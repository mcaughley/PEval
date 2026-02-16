# app.py - Final version with auto-generated standards-based compliance table

import streamlit as st
from pypdf import PdfReader
import re
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="CBKM Pontoon Evaluator", layout="wide")

st.title("CBKM Pontoon Design Evaluator")
st.markdown("""
Upload your pontoon design PDF to extract parameters and check compliance against:
- AS 3962:2020 (Marina design)
- AS 4997:2005 (Maritime structures)
- AS/NZS 1170.2:2021 (Wind actions)
- AS 3600:2018 (Concrete structures)
- QLD Tidal Works Code (Coastal Protection & Management Regulation 2017)
""")

uploaded_file = st.file_uploader("Upload PDF Drawings", type="pdf")

if uploaded_file is not None:
    try:
        reader = PdfReader(uploaded_file)
        full_text = ""
        for page in reader.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"

        st.success(f"PDF processed ({len(reader.pages)} pages). Extracting parameters...")

        # Extract parameters using tuned regex
        params = {}

        # Live loads
        match = re.search(r"LIVE LOAD (\d+\.\d+) kPa OR POINT LOAD (\d+\.\d+)kN", full_text, re.I)
        if match:
            params['live_load_uniform'] = float(match.group(1))
            params['live_load_point'] = float(match.group(2))

        # Wind
        match = re.search(r"ULTIMATE WIND SPEED V100 = (\d+)m/s", full_text, re.I)
        if match:
            params['wind_ultimate'] = int(match.group(1))

        # Wave height
        match = re.search(r"DESIGN WAVE HEIGHT<(\d+)mm", full_text, re.I)
        if match:
            params['wave_height'] = int(match.group(1)) / 1000.0

        # Current velocity
        match = re.search(r"DESIGN STREAM VELOCITY .* <(\d+\.\d+) m/s", full_text, re.I)
        if match:
            params['current_velocity'] = float(match.group(1))

        # Debris
        match = re.search(r"DEBRIS LOADS = (\d+\.\d+)m DEEP DEBRIS MAT, OR (\d+\.\d+) TONNE LOG", full_text, re.I)
        if match:
            params['debris_mat_depth'] = float(match.group(1))
            params['debris_log_mass'] = float(match.group(2))

        # Vessel
        match = re.search(r"VESSEL LENGTH = (\d+\.\d+) m", full_text, re.I)
        if match:
            params['vessel_length'] = float(match.group(1))
        match = re.search(r"VESSEL BEAM = (\d+\.\d+) m", full_text, re.I)
        if match:
            params['vessel_beam'] = float(match.group(1))
        match = re.search(r"VESSEL MASS = (\d+,\d+) kg", full_text, re.I)
        if match:
            params['vessel_mass'] = int(match.group(1).replace(',', ''))

        # Freeboard
        match = re.search(r"DEAD LOAD ONLY = (\d+)-(\d+)mm", full_text, re.I)
        if match:
            params['freeboard_dead_min'] = int(match.group(1))
            params['freeboard_dead_max'] = int(match.group(2))
            params['freeboard_dead'] = (params['freeboard_dead_min'] + params['freeboard_dead_max']) / 2
        match = re.search(r"CRITICAL FLOTATION/STABILITY CASE = MIN (\d+) mm", full_text, re.I)
        if match:
            params['freeboard_critical'] = int(match.group(1))

        # Deck slope
        match = re.search(r"CRITICAL DECK SLOPE = 1:(\d+) DEG", full_text, re.I)
        if match:
            params['deck_slope_max'] = int(match.group(1))

        # Concrete
        match = re.search(r"PONTOON CONCRETE STRENGTH TO BE (\d+) MPa", full_text, re.I)
        if match:
            params['concrete_strength'] = int(match.group(1))
        match = re.search(r"MINIMUM COVER TO THE REINFORCEMENT - (\d+) mm", full_text, re.I)
        if match:
            params['concrete_cover'] = int(match.group(1))

        # Steel galvanizing
        match = re.search(r"COATING MASS NOT LESS THAN (\d+) g/sqm", full_text, re.I)
        if match:
            params['steel_galvanizing'] = int(match.group(1))

        # Aluminium grade
        match = re.search(r"MINIMUM GRADE (\d+ T\d) U.N.O", full_text, re.I)
        if match:
            params['aluminium_grade'] = match.group(1)

        # Timber grade
        match = re.search(r"MINIMUM (F\d+)", full_text, re.I)
        if match:
            params['timber_grade'] = match.group(1)

        # Fixings
        match = re.search(r"FIXINGS TO BE (\d+) GRADE STAINLESS STEEL", full_text, re.I)
        if match:
            params['fixings_grade'] = int(match.group(1))

        # Scour allowance
        match = re.search(r"MAX (\d+)mm SCOUR", full_text, re.I)
        if match:
            params['scour_allowance'] = int(match.group(1))

        # Pile tolerance
        match = re.search(r"MAX OUT-OF-PLANE TOLERANCE .* = (\d+)mm", full_text, re.I)
        if match:
            params['pile_tolerance'] = int(match.group(1))

        # Soil cohesion
        match = re.search(r"UNDRAINED COHESION = (\d+)kPa", full_text, re.I)
        if match:
            params['soil_cohesion'] = int(match.group(1))

        # Display extracted parameters
        st.subheader("Extracted Parameters from Drawings")
        if params:
            df_params = pd.DataFrame(list(params.items()), columns=["Parameter", "Value"])
            st.dataframe(df_params, use_container_width=True)
        else:
            st.warning("No parameters extracted. Ensure PDF has selectable text.")

        # Auto-generate compliance table from params (standards-based checks)
        st.subheader("Compliance Summary (Automated Checks Against Standards)")

        checks = []

        # Live load uniform
        required_live_uniform = 3.0  # AS 3962:2020 unrestricted pontoons
        value = params.get('live_load_uniform', None)
        status = "Compliant" if value and value >= required_live_uniform else "Review"
        checks.append({
            "Check": "Live load uniform",
            "Required Value": f"≥ {required_live_uniform} kPa (unrestricted access pontoons)",
            "Your Design Value": value if value else "N/A",
            "Status": status,
            "Standard Reference": "AS 3962:2020 Section 2 & 4"
        })

        # Live load point
        required_live_point = 4.5  # AS 3962:2020 typical concentrated
        value = params.get('live_load_point', None)
        status = "Compliant" if value and value >= required_live_point else "Review"
        checks.append({
            "Check": "Live load point",
            "Required Value": f"≥ {required_live_point} kN (concentrated load)",
            "Your Design Value": value if value else "N/A",
            "Status": status,
            "Standard Reference": "AS 3962:2020 Section 4"
        })

        # Wind ultimate
        required_wind_ultimate = 64  # AS/NZS 1170.2:2021 Region C coastal QLD min
        value = params.get('wind_ultimate', None)
        status = "Compliant" if value and value >= required_wind_ultimate else "Review"
        checks.append({
            "Check": "Wind ultimate (Region C coastal)",
            "Required Value": "≈64–66 m/s (R=500 yr)",
            "Your Design Value": value if value else "N/A",
            "Status": status,
            "Standard Reference": "AS/NZS 1170.2:2021 Clause 3.2"
        })

        # Wave height
        required_wave = 0.5  # AS 3962:2020 typical sheltered estuarine max
        value = params.get('wave_height', None)
        status = "Compliant" if value and value <= required_wave else "Review"
        checks.append({
            "Check": "Design wave height",
            "Required Value": "Typically <0.5–1.0 m sheltered estuarine",
            "Your Design Value": value if value else "N/A",
            "Status": status,
            "Standard Reference": "AS 3962:2020 Section 2.3.3"
        })

        # Current velocity
        required_current = 1.5  # AS 3962:2020 typical estuarine
        value = params.get('current_velocity', None)
        status = "Compliant" if value and value <= required_current else "Review"
        checks.append({
            "Check": "Design current velocity",
            "Required Value": "Typically <1.5–2.0 m/s estuarine",
            "Your Design Value": value if value else "N/A",
            "Status": status,
            "Standard Reference": "AS 3962:2020 Section 2"
        })

        # Debris mat depth
        required_debris_mat = 1.0  # AS 4997:2005 site-specific; typical 1-2 m
        value = params.get('debris_mat_depth', None)
        status = "Compliant" if value and value >= required_debris_mat else "Review"
        checks.append({
            "Check": "Debris mat depth",
            "Required Value": "Site-specific; typically 1-2 m",
            "Your Design Value": value if value else "N/A",
            "Status": status,
            "Standard Reference": "AS 4997:2005 Section 3"
        })

        # Freeboard dead load
        required_freeboard_dead = 300  # AS 3962:2020 typical 300-600 mm
        value = params.get('freeboard_dead', None)
        status = "Compliant" if value and value >= required_freeboard_dead else "Review"
        checks.append({
            "Check": "Freeboard (dead load)",
            "Required Value": "Typically 300-600 mm",
            "Your Design Value": value if value else "N/A",
            "Status": status,
            "Standard Reference": "AS 3962:2020 Section 3"
        })

        # Freeboard critical
        required_freeboard_crit = 50  # AS 4997:2005 min 50 mm or 5% depth
        value = params.get('freeboard_critical', None)
        status = "Compliant" if value and value >= required_freeboard_crit else "Review"
        checks.append({
            "Check": "Freeboard (critical case)",
            "Required Value": "Min 50 mm under adverse loads",
            "Your Design Value": value if value else "N/A",
            "Status": status,
            "Standard Reference": "AS 4997:2005 Section 4"
        })

        # Deck slope max
        required_deck_slope = 10  # AS 3962:2020 <10° under stability load
        value = params.get('deck_slope_max', None)
        status = "Compliant" if value and value < required_deck_slope else "Review"
        checks.append({
            "Check": "Max deck slope/heel",
            "Required Value": "<10° under stability load",
            "Your Design Value": value if value else "N/A",
            "Status": status,
            "Standard Reference": "AS 3962:2020 Section 3"
        })

        # Concrete strength
        required_conc_strength = 40  # AS 3600:2018 min 40-50 MPa marine
        value = params.get('concrete_strength', None)
        status = "Compliant" if value and value >= required_conc_strength else "Review"
        checks.append({
            "Check": "Pontoon concrete strength",
            "Required Value": "Min 40–50 MPa marine grade",
            "Your Design Value": value if value else "N/A",
            "Status": status,
            "Standard Reference": "AS 3600:2018 Table 4.3"
        })

        # Concrete cover
        required_conc_cover = 50  # AS 3600:2018 C1:50 mm; C2:65 mm
        value = params.get('concrete_cover', None)
        status = "Conditional" if value and value >= required_conc_cover else "Review"
        checks.append({
            "Check": "Concrete cover",
            "Required Value": "50 mm (C1); 65 mm (C2 tidal/splash)",
            "Your Design Value": value if value else "N/A",
            "Status": status,
            "Standard Reference": "AS 3600:2018 Table 4.3"
        })

        # Steel galvanizing
        required_galv = 600  # AS 3962:2020 ≥600 g/m² marine
        value = params.get('steel_galvanizing', None)
        status = "Compliant" if value and value >= required_galv else "Review"
        checks.append({
            "Check": "Steel galvanizing",
            "Required Value": "≥600 g/m² for marine exposure",
            "Your Design Value": value if value else "N/A",
            "Status": status,
            "Standard Reference": "AS 3962:2020 Section 4-5"
        })

        # Aluminium grade
        required_alum = "6061-T6"  # AS 1664 common for marine gangway
        value = params.get('aluminium_grade', None)
        status = "Compliant" if value and value == required_alum else "Review"
        checks.append({
            "Check": "Aluminium grade",
            "Required Value": "Min 6061-T6 or equivalent",
            "Your Design Value": value if value else "N/A",
            "Status": status,
            "Standard Reference": "AS 1664"
        })

        # Timber grade
        required_timber = "F17"  # AS 3962:2020 min F17
        value = params.get('timber_grade', None)
        status = "Compliant" if value and value == required_timber else "Review"
        checks.append({
            "Check": "Timber grade",
            "Required Value": "Min F17",
            "Your Design Value": value if value else "N/A",
            "Status": status,
            "Standard Reference": "AS 3962:2020 Section 4-5"
        })

        # Fixings
        required_fixings = 316  # AS 3962:2020 316 SS marine
        value = params.get('fixings_grade', None)
        status = "Compliant" if value and value == required_fixings else "Review"
        checks.append({
            "Check": "Fixings",
            "Required Value": "316 grade SS",
            "Your Design Value": value if value else "N/A",
            "Status": status,
            "Standard Reference": "AS 3962:2020 Section 4-5"
        })

        # Scour allowance
        required_scour = 300  # AS 4997:2005 site-specific; typical 300-1000 mm allowance
        value = params.get('scour_allowance', None)
        status = "Compliant" if value and value >= required_scour else "Review"
        checks.append({
            "Check": "Max scour allowance",
            "Required Value": "Site-specific; typically 300-1000 mm",
            "Your Design Value": value if value else "N/A",
            "Status": status,
            "Standard Reference": "AS 4997:2005 Section 3"
        })

        # Pile tolerance
        required_pile_tol = 100  # AS 3962:2020 construction tolerance
        value = params.get('pile_tolerance', None)
        status = "Compliant" if value and value <= required_pile_tol else "Review"
        checks.append({
            "Check": "Pile out-of-plane tolerance",
            "Required Value": "≤100 mm",
            "Your Design Value": value if value else "N/A",
            "Status": status,
            "Standard Reference": "AS 3962:2020 Section 4"
        })

        # Soil cohesion
        required_soil_cohesion = 100  # Site-specific; typical ≥100-125 kPa estuarine
        value = params.get('soil_cohesion', None)
        status = "Compliant" if value and value >= required_soil_cohesion else "Review"
        checks.append({
            "Check": "Soil cohesion",
            "Required Value": "Site-specific; typically ≥100-125 kPa estuarine",
            "Your Design Value": value if value else "N/A",
            "Status": status,
            "Standard Reference": "AS 4997:2005 Section 4 (geotech assumptions)"
        })

        # Display table with color styling
        df_checks = pd.DataFrame(checks)
        st.dataframe(
            df_checks.style.applymap(
                lambda v: "background-color: #d4edda; color: #155724" if v == "Compliant" else "background-color: #fff3cd; color: #856404" if v == "Conditional" else "background-color: #f8d7da; color: #721c24",
                subset=["Status"]
            ),
            use_container_width=True
        )

        # Download report
        report_md = f"# CBKM Pontoon Compliance Report\n**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        report_md += "## Extracted Parameters\n" + df_params.to_markdown(index=False) + "\n\n"
        report_md += "## Compliance Summary\n" + df_checks.to_markdown(index=False)

        st.download_button(
            label="Download Full Report (Markdown)",
            data=report_md,
            file_name="pontoon_compliance_report.md",
            mime="text/markdown"
        )

    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")

else:
    st.info("Upload a PDF to start.")
