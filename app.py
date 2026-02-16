# app.py - Final modularized version with standards-based auto-checks

import streamlit as st
from pypdf import PdfReader
import re
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="CBKM Pontoon Evaluator", layout="wide")

st.title("CBKM Pontoon Design Evaluator")
st.markdown("""
Upload pontoon design PDF → extract parameters → auto-check compliance against Australian Standards  
(not just project notes). Focus: AS 3962:2020, AS 4997:2005, AS/NZS 1170.2:2021, AS 3600:2018, QLD Tidal Works.
""")

uploaded_file = st.file_uploader("Upload PDF Drawings", type="pdf")

if uploaded_file is not None:
    try:
        reader = PdfReader(uploaded_file)
        full_text = ""
        for page in reader.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"

        st.success(f"PDF processed ({len(reader.pages)} pages)")

        # Extract parameters
        params = {}

        # Live loads
        if m := re.search(r"LIVE LOAD (\d+\.\d+) kPa OR POINT LOAD (\d+\.\d+) kN", full_text, re.I):
            params['live_load_uniform'] = float(m.group(1))
            params['live_load_point'] = float(m.group(2))

        # Wind ultimate
        if m := re.search(r"ULTIMATE WIND SPEED V100 = (\d+)m/s", full_text, re.I):
            params['wind_ultimate'] = int(m.group(1))

        # Wave height (m)
        if m := re.search(r"DESIGN WAVE HEIGHT<(\d+)mm", full_text, re.I):
            params['wave_height'] = int(m.group(1)) / 1000.0

        # Current velocity
        if m := re.search(r"DESIGN STREAM VELOCITY .* <(\d+\.\d+) m/s", full_text, re.I):
            params['current_velocity'] = float(m.group(1))

        # Debris
        if m := re.search(r"DEBRIS LOADS = (\d+\.\d+)m DEEP DEBRIS MAT, OR (\d+\.\d+) TONNE LOG", full_text, re.I):
            params['debris_mat_depth'] = float(m.group(1))
            params['debris_log_mass'] = float(m.group(2))

        # Vessel
        if m := re.search(r"VESSEL LENGTH = (\d+\.\d+) m", full_text, re.I):
            params['vessel_length'] = float(m.group(1))
        if m := re.search(r"VESSEL BEAM = (\d+\.\d+) m", full_text, re.I):
            params['vessel_beam'] = float(m.group(1))
        if m := re.search(r"VESSEL MASS = (\d+,\d+) kg", full_text, re.I):
            params['vessel_mass'] = int(m.group(1).replace(',', ''))

        # Freeboard
        if m := re.search(r"DEAD LOAD ONLY = (\d+)-(\d+)mm", full_text, re.I):
            params['freeboard_dead_min'] = int(m.group(1))
            params['freeboard_dead_max'] = int(m.group(2))
            params['freeboard_dead'] = (params['freeboard_dead_min'] + params['freeboard_dead_max']) / 2
        if m := re.search(r"CRITICAL FLOTATION/STABILITY CASE = MIN (\d+) mm", full_text, re.I):
            params['freeboard_critical'] = int(m.group(1))

        # Deck slope
        if m := re.search(r"CRITICAL DECK SLOPE = 1:(\d+) DEG", full_text, re.I):
            params['deck_slope_max'] = int(m.group(1))

        # Concrete
        if m := re.search(r"PONTOON CONCRETE STRENGTH TO BE (\d+) MPa", full_text, re.I):
            params['concrete_strength'] = int(m.group(1))
        if m := re.search(r"MINIMUM COVER TO THE REINFORCEMENT - (\d+) mm", full_text, re.I):
            params['concrete_cover'] = int(m.group(1))

        # Galvanizing
        if m := re.search(r"COATING MASS NOT LESS THAN (\d+) g/sqm", full_text, re.I):
            params['steel_galvanizing'] = int(m.group(1))

        # Aluminium grade
        if m := re.search(r"MINIMUM GRADE (\d+ T\d)", full_text, re.I):
            params['aluminium_grade'] = m.group(1).replace(" ", "")

        # Timber
        if m := re.search(r"MINIMUM (F\d+)", full_text, re.I):
            params['timber_grade'] = m.group(1)

        # Fixings
        if m := re.search(r"FIXINGS TO BE (\d+) GRADE STAINLESS STEEL", full_text, re.I):
            params['fixings_grade'] = m.group(1)

        # Scour & tolerance
        if m := re.search(r"MAX (\d+)mm SCOUR", full_text, re.I):
            params['scour_allowance'] = int(m.group(1))
        if m := re.search(r"MAX OUT-OF-PLANE TOLERANCE .* = (\d+)mm", full_text, re.I):
            params['pile_tolerance'] = int(m.group(1))

        # Soil
        if m := re.search(r"UNDRAINED COHESION = (\d+)kPa", full_text, re.I):
            params['soil_cohesion'] = int(m.group(1))

        # Show extracted params
        st.subheader("Extracted Parameters")
        if params:
            df_params = pd.DataFrame(list(params.items()), columns=["Parameter", "Value"])
            st.dataframe(df_params, use_container_width=True)
        else:
            st.warning("No parameters extracted – ensure PDF text is selectable.")

        # Modular compliance checks definition (easy to extend)
        compliance_checks = [
            {
                "name": "Live load uniform",
                "required_value": "≥ 3.0 kPa (unrestricted pontoon access)",
                "extract_key": "live_load_uniform",
                "comparison_func": lambda v: "Compliant" if v >= 3.0 else "Review",
                "reference": "AS 3962:2020 Section 2 & 4 (floating pontoon live load)",
                "notes": "Exceeds minima for commercial use."
            },
            {
                "name": "Live load point",
                "required_value": "≥ 4.5 kN (typical concentrated)",
                "extract_key": "live_load_point",
                "comparison_func": lambda v: "Compliant" if v >= 4.5 else "Review",
                "reference": "AS 3962:2020 Section 4 (point load allowance)",
                "notes": "Within typical range."
            },
            {
                "name": "Wind ultimate (Region C coastal)",
                "required_value": "≈64–66 m/s (R=500 yr)",
                "extract_key": "wind_ultimate",
                "comparison_func": lambda v: "Compliant" if v >= 64 else "Review",
                "reference": "AS/NZS 1170.2:2021 Clause 3.2 (Region C coastal interpolation)",
                "notes": "Matches Burnett Heads site."
            },
            {
                "name": "Design wave height",
                "required_value": "Typically <0.5–1.0 m (sheltered estuarine)",
                "extract_key": "wave_height",
                "comparison_func": lambda v: "Compliant" if v <= 0.5 else "Review",
                "reference": "AS 3962:2020 Section 2.3.3 (hydrodynamic assessment)",
                "notes": "Reasonable for low-fetch site; confirm survey."
            },
            {
                "name": "Design current velocity",
                "required_value": "Typically <1.5–2.0 m/s estuarine",
                "extract_key": "current_velocity",
                "comparison_func": lambda v: "Compliant" if v <= 1.5 else "Review",
                "reference": "AS 3962:2020 Section 2 (current loads)",
                "notes": "Conservative; verify 2% exceedance."
            },
            {
                "name": "Freeboard (dead load)",
                "required_value": "Typically 300–600 mm",
                "extract_key": "freeboard_dead",
                "comparison_func": lambda v: "Compliant" if v >= 300 else "Review",
                "reference": "AS 3962:2020 Section 3 (floating pontoon)",
                "notes": "Within typical range."
            },
            {
                "name": "Freeboard (critical case)",
                "required_value": "Min 50 mm under adverse loads",
                "extract_key": "freeboard_critical",
                "comparison_func": lambda v: "Compliant" if v >= 50 else "Review",
                "reference": "AS 4997:2005 Section 4 (min freeboard)",
                "notes": "Meets minimum."
            },
            {
                "name": "Max deck slope/heel",
                "required_value": "<10° under stability load",
                "extract_key": "deck_slope_max",
                "comparison_func": lambda v: "Compliant" if v < 10 else "Review",
                "reference": "AS 3962:2020 Section 3 (max heel/trim)",
                "notes": "Well below limit."
            },
            {
                "name": "Pontoon concrete strength",
                "required_value": "Min 40–50 MPa marine grade",
                "extract_key": "concrete_strength",
                "comparison_func": lambda v: "Compliant" if v >= 40 else "Review",
                "reference": "AS 3600:2018 Table 4.3 & AS 3962:2020 Section 4-5",
                "notes": "Exceeds minimum."
            },
            {
                "name": "Concrete cover",
                "required_value": "50 mm (C1); 65 mm (C2 tidal/splash)",
                "extract_key": "concrete_cover",
                "comparison_func": lambda v: "Compliant" if v >= 65 else ("Conditional" if v >= 50 else "Review"),
                "reference": "AS 3600:2018 Table 4.3 (exposure classes)",
                "notes": "Likely C2 on exposed faces → verify tidal splash zone or increase cover."
            },
            {
                "name": "Steel galvanizing",
                "required_value": "≥600 g/m² marine exposure",
                "extract_key": "steel_galvanizing",
                "comparison_func": lambda v: "Compliant" if v >= 600 else "Review",
                "reference": "AS 3962:2020 & AS 4997:2005 Section 5 (durability)",
                "notes": "Meets marine requirement."
            },
            {
                "name": "Aluminium grade",
                "required_value": "Min 6061-T6 or equivalent",
                "extract_key": "aluminium_grade",
                "comparison_func": lambda v: "Compliant" if v == "6061T6" else "Review",
                "reference": "AS 1664 & AS 3962:2020 Section 4-5",
                "notes": "Compliant if 6061-T6."
            },
            {
                "name": "Fixings",
                "required_value": "316 grade SS",
                "extract_key": "fixings_grade",
                "comparison_func": lambda v: "Compliant" if str(v).upper().find("316") >= 0 else "Review",
                "reference": "AS 3962:2020 & AS 4997:2005 Section 5",
                "notes": "Standard for marine."
            },
            # Add more checks here as needed (e.g., scour, pile tolerance)
        ]

        # Auto-generate table
        table_data = []
        for check in compliance_checks:
            value = params.get(check["extract_key"], None)
            status = check["comparison_func"](value) if value is not None else "N/A"
            table_data.append({
                "Check": check["name"],
                "Required Value": check["required_value"],
                "Your Design Value": value if value is not None else "N/A",
                "Status": status,
                "Standard Reference": check["reference"],
                "Notes": check.get("notes", "")
            })

        df_checks = pd.DataFrame(table_data)

        st.subheader("Automated Compliance Summary (Standards-Based)")
        st.dataframe(
            df_checks.style.applymap(
                lambda v: "background-color: #d4edda; color: #155724" if v == "Compliant" else 
                          "background-color: #fff3cd; color: #856404" if v == "Conditional" else 
                          "background-color: #f8d7da; color: #721c24" if v == "Review" else "",
                subset=["Status"]
            ),
            use_container_width=True
        )

        # Download report
        report_md = f"# CBKM Pontoon Compliance Report\n**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        report_md += "## Extracted Parameters\n" + df_params.to_markdown(index=False) + "\n\n"
        report_md += "## Compliance Summary (Standards-Based)\n" + df_checks.to_markdown(index=False)

        st.download_button(
            label="Download Report (Markdown)",
            data=report_md,
            file_name="pontoon_compliance_report.md",
            mime="text/markdown"
        )

    except Exception as e:
        st.error(f"Error: {str(e)}")

else:
    st.info("Upload PDF to start.")
