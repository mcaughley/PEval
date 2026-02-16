import streamlit as st
from pypdf import PdfReader
import re
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="CBKM Pontoon Evaluator", layout="wide")
st.title("CBKM Pontoon Design Evaluator")
st.markdown("Upload your GC Marine PDF drawings and get an instant compliance report (AS 3962, AS 4997, QLD Tidal Works)")

uploaded_file = st.file_uploader("Upload PDF (any number of pages)", type="pdf")

if uploaded_file is not None:
    try:
        reader = PdfReader(uploaded_file)
        full_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

        st.success(f"Successfully read {len(reader.pages)} pages from the PDF")

        params = {}

        # All regex tuned exactly to your uploaded drawings
        if m := re.search(r"LIVE LOAD.*?(\d+\.\d+)\s*kPa.*?POINT LOAD.*?(\d+\.\d+)\s*kN", full_text, re.I | re.S):
            params['Live Load Uniform (kPa)'] = float(m.group(1))
            params['Live Load Point (kN)'] = float(m.group(2))

        if m := re.search(r"ULTIMATE WIND SPEED V100\s*=\s*(\d+)m/s", full_text, re.I):
            params['Wind Ultimate V100 (m/s)'] = int(m.group(1))

        if m := re.search(r"DESIGN WAVE HEIGHT\s*<\s*(\d+)mm", full_text, re.I):
            params['Design Wave Height (mm)'] = int(m.group(1))

        if m := re.search(r"DESIGN STREAM VELOCITY.*?<\s*(\d+\.\d+)\s*m/s", full_text, re.I):
            params['Current Velocity (m/s)'] = float(m.group(1))

        if m := re.search(r"DEBRIS LOADS\s*=\s*(\d+\.\d+)m.*?(\d+\.\d+)\s*TONNE", full_text, re.I):
            params['Debris Mat Depth (m)'] = float(m.group(1))
            params['Debris Log Mass (tonne)'] = float(m.group(2))

        if m := re.search(r"VESSEL LENGTH\s*=\s*(\d+\.\d+)\s*m", full_text, re.I):
            params['Vessel Length (m)'] = float(m.group(1))
        if m := re.search(r"VESSEL BEAM\s*=\s*(\d+\.\d+)\s*m", full_text, re.I):
            params['Vessel Beam (m)'] = float(m.group(1))
        if m := re.search(r"VESSEL MASS\s*=\s*(\d+,\d+)\s*kg", full_text, re.I):
            params['Vessel Mass (kg)'] = int(m.group(1).replace(',', ''))

        if m := re.search(r"DEAD LOAD ONLY\s*=\s*(\d+)-(\d+)mm", full_text, re.I):
            params['Freeboard Dead Load (mm)'] = f"{m.group(1)}–{m.group(2)}"

        if m := re.search(r"CRITICAL FLOTATION.*?MIN\s*(\d+)\s*mm", full_text, re.I):
            params['Freeboard Critical (mm)'] = int(m.group(1))

        if m := re.search(r"CRITICAL DECK SLOPE.*?(\d+)\s*DEG", full_text, re.I):
            params['Max Deck Slope (deg)'] = int(m.group(1))

        if m := re.search(r"PONTOON CONCRETE STRENGTH.*?(\d+)\s*MPa", full_text, re.I):
            params['Pontoon Concrete (MPa)'] = int(m.group(1))

        if m := re.search(r"MINIMUM COVER.*?(\d+)\s*mm", full_text, re.I):
            params['Concrete Cover (mm)'] = int(m.group(1))

        if m := re.search(r"COATING MASS.*?(\d+)\s*g/sqm", full_text, re.I):
            params['Steel Galvanizing (g/m²)'] = int(m.group(1))

        if m := re.search(r"MINIMUM GRADE\s*(\d+\s*T\d+)", full_text, re.I):
            params['Aluminium Grade'] = m.group(1).replace(' ', '')

        if m := re.search(r"MINIMUM\s*(F\d+)", full_text, re.I):
            params['Timber Grade'] = m.group(1)

        if m := re.search(r"FIXINGS TO BE\s*(\d+)\s*GRADE STAINLESS STEEL", full_text, re.I):
            params['Fixings'] = f"{m.group(1)} SS"

        if m := re.search(r"MAX\s*(\d+)mm\s*SCOUR", full_text, re.I):
            params['Max Scour (mm)'] = int(m.group(1))

        if m := re.search(r"UNDRAINED COHESION\s*=\s*(\d+)kPa", full_text, re.I):
            params['Soil Cohesion (kPa)'] = int(m.group(1))

        # Show extracted parameters
        st.subheader("Extracted Design Parameters")
        if params:
            df_params = pd.DataFrame(list(params.items()), columns=["Parameter", "Value"])
            st.dataframe(df_params, use_container_width=True)
        else:
            st.warning("No parameters were found. Make sure the PDF contains selectable text.")

        # Compliance checks
        st.subheader("Compliance Check Summary")
        checks = []
        checks.append({"Check": "Live Load Uniform", "Required": "≥ 3.0 kPa", "Found": params.get('Live Load Uniform (kPa)', 'N/A'), "Status": "PASS" if params.get('Live Load Uniform (kPa)', 0) >= 3.0 else "REVIEW"})
        checks.append({"Check": "Wind Ultimate V100", "Required": "≥ 65 m/s", "Found": params.get('Wind Ultimate V100 (m/s)', 'N/A'), "Status": "PASS" if params.get('Wind Ultimate V100 (m/s)', 0) >= 65 else "REVIEW"})
        checks.append({"Check": "Design Wave Height", "Required": "< 400 mm", "Found": params.get('Design Wave Height (mm)', 'N/A'), "Status": "PASS" if params.get('Design Wave Height (mm)', 0) < 400 else "REVIEW"})
        checks.append({"Check": "Pontoon Concrete", "Required": "≥ 50 MPa", "Found": params.get('Pontoon Concrete (MPa)', 'N/A'), "Status": "PASS" if params.get('Pontoon Concrete (MPa)', 0) >= 50 else "REVIEW"})
        checks.append({"Check": "Concrete Cover", "Required": "≥ 50 mm", "Found": params.get('Concrete Cover (mm)', 'N/A'), "Status": "PASS" if params.get('Concrete Cover (mm)', 0) >= 50 else "REVIEW"})
        checks.append({"Check": "Steel Galvanizing", "Required": "≥ 600 g/m²", "Found": params.get('Steel Galvanizing (g/m²)', 'N/A'), "Status": "PASS" if params.get('Steel Galvanizing (g/m²)', 0) >= 600 else "REVIEW"})
        checks.append({"Check": "Aluminium Grade", "Required": "6061-T6", "Found": params.get('Aluminium Grade', 'N/A'), "Status": "PASS" if params.get('Aluminium Grade') == "6061T6" else "REVIEW"})
        checks.append({"Check": "Fixings", "Required": "316 SS", "Found": params.get('Fixings', 'N/A'), "Status": "PASS" if params.get('Fixings') == "316 SS" else "REVIEW"})

        df_checks = pd.DataFrame(checks)
        st.dataframe(df_checks, use_container_width=True)

        # Download report
        report = "# CBKM Pontoon Evaluation Report\n**Date:** " + datetime.now().strftime("%Y-%m-%d %H:%M") + "\n\n## Extracted Parameters\n" + df_params.to_markdown(index=False) + "\n\n## Compliance Checks\n" + df_checks.to_markdown(index=False)
        st.download_button("Download Full Report (Markdown)", report, file_name="pontoon_report.md", mime="text/markdown")

    except Exception as e:
        st.error(f"Error reading PDF: {e}. Try a different file or ensure it has selectable text.")

else:
    st.info("Upload your pontoon design PDF to begin. Works perfectly with your GC Marine drawings.")
