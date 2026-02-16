# app.py - Pontoon Design Evaluator (clean version for Snowflake / Streamlit)
import streamlit as st
import pypdf2
import re
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="CBKM Pontoon Evaluator", layout="wide")

st.title("CBKM Pontoon Design Evaluator")
st.markdown("Upload PDF drawings → extract key parameters → check compliance with AS 3962 / AS 4997 / QLD tidal works")

uploaded_file = st.file_uploader("Upload PDF (multi-page drawings)", type="pdf")

if uploaded_file is not None:
    try:
        reader = pypdf2.PdfReader(uploaded_file)
        full_text = ""
        for page in reader.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"

        st.success(f"PDF processed ({len(reader.pages)} pages)")

        # Extract parameters - tuned to your exact drawing text
        params = {}

        # Live loads (from GENERAL)
        match = re.search(r"LIVE LOAD.*?(\d+\.\d+)\s*kPa.*?POINT LOAD.*?(\d+\.\d+)\s*kN", full_text, re.IGNORECASE | re.DOTALL)
        if match:
            params['live_load_uniform'] = float(match.group(1))
            params['live_load_point'] = float(match.group(2))

        # Wind
        match = re.search(r"ULTIMATE WIND SPEED V100\s*=\s*(\d+)m/s", full_text, re.IGNORECASE)
        if match:
            params['wind_ultimate'] = int(match.group(1))

        # Wave height
        match = re.search(r"DESIGN WAVE HEIGHT\s*<\s*(\d+)mm", full_text, re.IGNORECASE)
        if match:
            params['wave_height_mm'] = int(match.group(1))
            params['wave_height'] = params['wave_height_mm'] / 1000.0

        # Current velocity
        match = re.search(r"DESIGN STREAM VELOCITY.*?<\s*(\d+\.\d+)\s*m/s", full_text, re.IGNORECASE)
        if match:
            params['current_velocity'] = float(match.group(1))

        # Debris
        match = re.search(r"DEBRIS LOADS.*?(\d+\.\d+)m.*?(\d+\.\d+)\s*TONNE", full_text, re.IGNORECASE)
        if match:
            params['debris_mat_depth'] = float(match.group(1))
            params['debris_log_mass'] = float(match.group(2))

        # Vessel
        match = re.search(r"VESSEL LENGTH\s*=\s*(\d+\.\d+)\s*m", full_text, re.IGNORECASE)
        if match:
            params['vessel_length'] = float(match.group(1))
        match = re.search(r"VESSEL BEAM\s*=\s*(\d+\.\d+)\s*m", full_text, re.IGNORECASE)
        if match:
            params['vessel_beam'] = float(match.group(1))
        match = re.search(r"VESSEL MASS\s*=\s*(\d+,\d+)\s*kg", full_text, re.IGNORECASE)
        if match:
            params['vessel_mass'] = int(match.group(1).replace(',', ''))

        # Freeboard
        match = re.search(r"DEAD LOAD ONLY\s*=\s*(\d+)-(\d+)mm", full_text, re.IGNORECASE)
        if match:
            params['freeboard_dead'] = (int(match.group(1)) + int(match.group(2))) / 2
        match = re.search(r"MIN\s*(\d+)\s*mm", full_text, re.IGNORECASE)
        if match:
            params['freeboard_critical'] = int(match.group(1))

        # Deck slope
        match = re.search(r"CRITICAL DECK SLOPE.*?(\d+)\s*DEG", full_text, re.IGNORECASE)
        if match:
            params['deck_slope_max'] = int(match.group(1))

        # Concrete
        match = re.search(r"PONTOON CONCRETE STRENGTH.*?(\d+)\s*MPa", full_text, re.IGNORECASE)
        if match:
            params['concrete_strength'] = int(match.group(1))
        match = re.search(r"COVER.*?(\d+)\s*mm", full_text, re.IGNORECASE)
        if match:
            params['concrete_cover'] = int(match.group(1))

        # Galvanizing
        match = re.search(r"COATING MASS.*?(\d+)\s*g/sqm", full_text, re.IGNORECASE)
        if match:
            params['steel_galvanizing'] = int(match.group(1))

        # Aluminium grade
        match = re.search(r"MINIMUM GRADE\s*(\d+\s*T\d+)", full_text, re.IGNORECASE)
        if match:
            params['aluminium_grade'] = match.group(1).replace(" ", "")

        # Timber grade
        match = re.search(r"MINIMUM\s*(F\d+)", full_text, re.IGNORECASE)
        if match:
            params['timber_grade'] = match.group(1)

        # Fixings
        match = re.search(r"FIXINGS TO BE\s*(\d+)\s*GRADE STAINLESS STEEL", full_text, re.IGNORECASE)
        if match:
            params['fixings_grade'] = f"{match.group(1)} SS"

        # Scour & tolerances
        match = re.search(r"MAX\s*(\d+)mm\s*SCOUR", full_text, re.IGNORECASE)
        if match:
            params['scour_allowance'] = int(match.group(1))
        match = re.search(r"TOLERANCE.*?(\d+)mm", full_text, re.IGNORECASE)
        if match:
            params['pile_tolerance'] = int(match.group(1))

        match = re.search(r"UNDRAINED COHESION\s*=\s*(\d+)kPa", full_text, re.IGNORECASE)
        if match:
            params['soil_cohesion'] = int(match.group(1))

        # Fill missing with defaults / estimates
        if 'vessel_length' in params:
            params.setdefault('berth_length', params['vessel_length'] * 1.1)
        if 'vessel_beam' in params:
            params.setdefault('berth_width', params['vessel_beam'] * 1.5)

        st.subheader("Extracted Parameters")
        if params:
            df_params = pd.DataFrame(list(params.items()), columns=["Parameter", "Value"])
            st.dataframe(df_params, use_container_width=True)
        else:
            st.warning("No parameters found in the PDF text.")

        # Basic compliance checks (expand as needed)
        st.subheader("Quick Compliance Summary")

        checks = []

        if 'live_load_uniform' in params and params['live_load_uniform'] >= 3.0:
            checks.append({"Check": "Live load uniform", "Value": params['live_load_uniform'], "Status": "OK (≥3.0 kPa)"})
        else:
            checks.append({"Check": "Live load uniform", "Value": params.get('live_load_uniform', 'N/A'), "Status": "Review"})

        if 'wind_ultimate' in params and params['wind_ultimate'] >= 65:
            checks.append({"Check": "Wind ultimate (Region C)", "Value": params['wind_ultimate'], "Status": "OK (≥65 m/s)"})
        else:
            checks.append({"Check": "Wind ultimate", "Value": params.get('wind_ultimate', 'N/A'), "Status": "Review"})

        if 'wave_height' in params and params['wave_height'] <= 0.4:
            checks.append({"Check": "Design wave height", "Value": params['wave_height'], "Status": "OK (<400 mm)"})
        else:
            checks.append({"Check": "Wave height", "Value": params.get('wave_height', 'N/A'), "Status": "Review"})

        if 'concrete_strength' in params and params['concrete_strength'] >= 50:
            checks.append({"Check": "Pontoon concrete", "Value": params['concrete_strength'], "Status": "OK (≥50 MPa marine)"})
        else:
            checks.append({"Check": "Concrete strength", "Value": params.get('concrete_strength', 'N/A'), "Status": "Review"})

        if 'concrete_cover' in params and params['concrete_cover'] >= 50:
            checks.append({"Check": "Concrete cover", "Value": params['concrete_cover'], "Status": "OK (≥50 mm)"})
        else:
            checks.append({"Check": "Concrete cover", "Value": params.get('concrete_cover', 'N/A'), "Status": "Review"})

        if 'steel_galvanizing' in params and params['steel_galvanizing'] >= 600:
            checks.append({"Check": "Steel galvanizing", "Value": params['steel_galvanizing'], "Status": "OK (≥600 g/m²)"})
        else:
            checks.append({"Check": "Galvanizing", "Value": params.get('steel_galvanizing', 'N/A'), "Status": "Review"})

        st.dataframe(pd.DataFrame(checks), use_container_width=True)

        # Download report
        report_md = f"# CBKM Evaluation Report\n**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        report_md += "## Extracted Parameters\n" + df_params.to_markdown(index=False) + "\n\n"
        report_md += "## Compliance Checks\n" + pd.DataFrame(checks).to_markdown(index=False)

        st.download_button("Download Report (Markdown)", report_md, file_name="pontoon_report.md")

    except Exception as e:
        st.error(f"Processing error: {str(e)}")

else:
    st.info("Upload the PDF to begin.")
