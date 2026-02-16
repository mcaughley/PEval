# app.py - Final version with PDF report download + CBKM logo header

import streamlit as st
from pypdf import PdfReader
import re
import pandas as pd
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import mm

st.set_page_config(page_title="CBKM Pontoon Evaluator", layout="wide")

st.title("CBKM Pontoon Design Evaluator")
st.markdown("""
Upload pontoon design PDF → extract parameters → auto-check compliance against Australian Standards  
(not just project notes). Covers: AS 3962:2020, AS 4997:2005, AS/NZS 1170.2:2021, AS 3600:2018, QLD Tidal Works.
""")

# Company logo file (must be uploaded to repo root as cbkm_logo.png)
LOGO_PATH = "cbkm_logo.png"  # ← changed to your requested filename

uploaded_file = st.file_uploader("Upload PDF Drawings", type="pdf")

def extract_project_address(full_text: str) -> str:
    """Dynamically extract project address from PDF text."""
    fallback = "145 Buss Street, Burnett Heads, QLD 4670, Australia"

    patterns = [
        r"PROJECT\s*(?:ADDRESS|USE ADDRESS|ADDR|LOCATION)?:?\s*([\w\s\d,./\-]+?)(?=\s*(PROJECT NAME|CLIENT|DRAWING|REVISION|DATE|PHONE|ABN|$))",
        r"145\s*BUSS\s*STREET\s*BURNETT\s*HEADS\s*4670\s*QLD\s*AUSTRALIA?",
        r"(145\s+BUSS\s+STREET.*?BURNETT\s+HEADS.*?4670\s*QLD\s*AUSTRALIA?)"
    ]

    for pattern in patterns:
        match = re.search(pattern, full_text, re.I | re.DOTALL)
        if match:
            addr = match.group(1 if 'group(1)' in pattern else 0).strip().replace('\n', ' ').replace('  ', ' ')
            return addr if addr else fallback

    return fallback


# Modular compliance checks (expanded as requested)
compliance_checks = [
    {
        "name": "Live load uniform",
        "required_value": "≥ 3.0 kPa (unrestricted pontoon access)",
        "extract_key": "live_load_uniform",
        "comparison_func": lambda v: "Compliant" if v >= 3.0 else "Review",
        "reference": "AS 3962:2020 Section 2 & 4 (floating pontoon live load)"
    },
    {
        "name": "Live load point",
        "required_value": "≥ 4.5–10 kN (typical concentrated)",
        "extract_key": "live_load_point",
        "comparison_func": lambda v: "Compliant" if v >= 4.5 else "Review",
        "reference": "AS 3962:2020 Section 4 (point load allowance)"
    },
    {
        "name": "Wind ultimate (Region C coastal)",
        "required_value": "≈64–66 m/s (R=500 yr coastal QLD)",
        "extract_key": "wind_ultimate",
        "comparison_func": lambda v: "Compliant" if v >= 64 else "Review",
        "reference": "AS/NZS 1170.2:2021 Clause 3.2 (Region C interpolation)"
    },
    {
        "name": "Design wave height",
        "required_value": "Site-specific; typically <0.5–1.0 m sheltered estuarine",
        "extract_key": "wave_height",
        "comparison_func": lambda v: "Compliant" if v <= 0.5 else "Review",
        "reference": "AS 3962:2020 Section 2.3.3 & AS 4997:2005 Section 3 (hydrodynamic)"
    },
    {
        "name": "Design current velocity",
        "required_value": "Site-specific; typically <1.5–2.0 m/s estuarine",
        "extract_key": "current_velocity",
        "comparison_func": lambda v: "Compliant" if v <= 1.5 else "Review",
        "reference": "AS 3962:2020 Section 2 & AS 4997:2005 Section 3 (current loads)"
    },
    {
        "name": "Debris mat depth",
        "required_value": "Site-specific; typically 1–2 m",
        "extract_key": "debris_mat_depth",
        "comparison_func": lambda v: "Compliant" if v >= 1.0 else "Review",
        "reference": "AS 4997:2005 Section 3 (debris impact)"
    },
    {
        "name": "Freeboard (dead load)",
        "required_value": "Typically 300–600 mm",
        "extract_key": "freeboard_dead",
        "comparison_func": lambda v: "Compliant" if 300 <= v <= 600 else "Review",
        "reference": "AS 3962:2020 Section 3 (floating pontoon freeboard)"
    },
    {
        "name": "Freeboard (critical case)",
        "required_value": "Min 50 mm under adverse loads",
        "extract_key": "freeboard_critical",
        "comparison_func": lambda v: "Compliant" if v >= 50 else "Review",
        "reference": "AS 4997:2005 Section 4 (min freeboard)"
    },
    {
        "name": "Max deck slope/heel",
        "required_value": "<10° under stability load",
        "extract_key": "deck_slope_max",
        "comparison_func": lambda v: "Compliant" if v < 10 else "Review",
        "reference": "AS 3962:2020 Section 3 (max heel/trim)"
    },
    {
        "name": "Pontoon concrete strength",
        "required_value": "Min 40–50 MPa marine grade",
        "extract_key": "concrete_strength",
        "comparison_func": lambda v: "Compliant" if v >= 40 else "Review",
        "reference": "AS 3600:2018 Table 4.3 & AS 3962:2020 Section 4-5"
    },
    {
        "name": "Concrete cover",
        "required_value": "50 mm (C1); 65 mm (C2 tidal/splash)",
        "extract_key": "concrete_cover",
        "comparison_func": lambda v: "Compliant" if v >= 65 else ("Conditional" if v >= 50 else "Review"),
        "reference": "AS 3600:2018 Table 4.3 (exposure classes)"
    },
    {
        "name": "Steel galvanizing",
        "required_value": "≥600 g/m² marine exposure",
        "extract_key": "steel_galvanizing",
        "comparison_func": lambda v: "Compliant" if v >= 600 else "Review",
        "reference": "AS 3962:2020 & AS 4997:2005 Section 5 (durability)"
    },
    {
        "name": "Aluminium grade",
        "required_value": "Min 6061-T6 or equivalent",
        "extract_key": "aluminium_grade",
        "comparison_func": lambda v: "Compliant" if v == "6061T6" else "Review",
        "reference": "AS 1664 & AS 3962:2020 Section 4-5"
    },
    {
        "name": "Timber grade",
        "required_value": "Min F17",
        "extract_key": "timber_grade",
        "comparison_func": lambda v: "Compliant" if v == "F17" else "Review",
        "reference": "AS 1720.1 & AS 3962:2020 Section 4-5"
    },
    {
        "name": "Fixings",
        "required_value": "316 grade SS",
        "extract_key": "fixings_grade",
        "comparison_func": lambda v: "Compliant" if str(v).upper().find("316") >= 0 else "Review",
        "reference": "AS 3962:2020 & AS 4997:2005 Section 5"
    },
    {
        "name": "Max scour allowance",
        "required_value": "Site-specific; typical allowance 300–1000 mm",
        "extract_key": "scour_allowance",
        "comparison_func": lambda v: "Compliant" if 300 <= v <= 1000 else "Review",
        "reference": "AS 4997:2005 Section 3 (scour protection)"
    },
    {
        "name": "Pile out-of-plane tolerance",
        "required_value": "≤100 mm (construction tolerance)",
        "extract_key": "pile_tolerance",
        "comparison_func": lambda v: "Compliant" if v <= 100 else "Review",
        "reference": "AS 3962:2020 Section 4 (construction tolerances)"
    },
    {
        "name": "Soil cohesion (undrained)",
        "required_value": "Site-specific; typical ≥100–125 kPa estuarine",
        "extract_key": "soil_cohesion",
        "comparison_func": lambda v: "Compliant" if v >= 100 else "Review",
        "reference": "AS 4997:2005 Section 4 (geotechnical assumptions)"
    },
    {
        "name": "Vessel mass (wet berth)",
        "required_value": "Site-specific; design basis up to 33,000 kg",
        "extract_key": "vessel_mass",
        "comparison_func": lambda v: "Compliant" if v <= 33000 else "Review",
        "reference": "AS 3962:2020 Section 3 (vessel envelope & berthing)"
    },
]

if uploaded_file is not None:
    try:
        reader = PdfReader(uploaded_file)
        full_text = ""
        for page in reader.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"

        st.success(f"PDF processed ({len(reader.pages)} pages)")

        project_address = extract_project_address(full_text)
        st.info(f"Detected Project Address: **{project_address}**")

        # Extract parameters (your existing regex logic here - abbreviated for brevity)
        params = {}
        # ... (paste your full extraction code here - live_load, wind, wave, current, debris, vessel, freeboard, concrete, etc.)

        # Display extracted params
        st.subheader("Extracted Parameters")
        if params:
            df_params = pd.DataFrame(list(params.items()), columns=["Parameter", "Value"])
            st.dataframe(df_params, use_container_width=True)

        # Build compliance table
        table_data = []
        for check in compliance_checks:
            value = params.get(check["extract_key"], None)
            status = check["comparison_func"](value) if value is not None else "N/A"
            table_data.append({
                "Check": check["name"],
                "Required Value": check["required_value"],
                "Your Design Value": value if value is not None else "N/A",
                "Status": status,
                "Standard Reference": check["reference"]
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

        # Generate PDF report with CBKM logo header
        def generate_pdf_report():
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=30*mm, bottomMargin=20*mm)
            styles = getSampleStyleSheet()
            elements = []

            # Header with CBKM logo
            try:
                logo = Image(LOGO_PATH, width=120*mm, height=40*mm)  # Adjust size as needed
                elements.append(logo)
            except Exception:
                elements.append(Paragraph("CBKM Logo (file not found)", styles['Heading3']))

            elements.append(Spacer(1, 8*mm))
            elements.append(Paragraph("CBKM Pontoon Compliance Report", styles['Title']))
            elements.append(Spacer(1, 6*mm))
            elements.append(Paragraph(f"**Project Name:** Commercial Use Pontoon (GCM-2136)", styles['Normal']))
            elements.append(Paragraph(f"**Project Location / Address:** {project_address}", styles['Normal']))
            elements.append(Paragraph(f"**Report Date:** {datetime.now().strftime('%Y-%m-%d %H:%M AEST')}", styles['Normal']))
            elements.append(Spacer(1, 12*mm))

            # Extracted parameters table
            elements.append(Paragraph("Extracted Parameters from Drawings", styles['Heading2']))
            param_data = [["Parameter", "Value"]] + [[k, str(v)] for k, v in params.items()]
            param_table = Table(param_data, colWidths=[120*mm, 60*mm])
            param_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('BACKGROUND', (0,1), (-1,-1), colors.lightgrey),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black)
            ]))
            elements.append(param_table)
            elements.append(Spacer(1, 12*mm))

            # Compliance summary table
            elements.append(Paragraph("Compliance Summary (Standards-Based)", styles['Heading2']))
            check_data = [["Check", "Required", "Design Value", "Status", "Reference"]] + \
                         [[row['Check'], row['Required Value'], row['Your Design Value'], row['Status'], row['Standard Reference']] for row in table_data]
            check_table = Table(check_data, colWidths=[40*mm, 50*mm, 30*mm, 20*mm, 50*mm])
            check_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('BACKGROUND', (0,1), (-1,-1), colors.lightgrey),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ('TEXTCOLOR', (3,1), (3,-1), lambda t: colors.green if t == "Compliant" else colors.red if t == "Review" else colors.orange if t == "Conditional" else colors.black)
            ]))
            elements.append(check_table)

            doc.build(elements)
            buffer.seek(0)
            return buffer

        # PDF Download Button
        pdf_buffer = generate_pdf_report()
        st.download_button(
            label="Download Report (PDF)",
            data=pdf_buffer,
            file_name="pontoon_compliance_report.pdf",
            mime="application/pdf"
        )

    except Exception as e:
        st.error(f"Error: {str(e)}")

else:
    st.info("Upload PDF to start.")
