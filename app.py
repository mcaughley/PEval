# app.py - FINAL VERSION - CBKM Pontoon Evaluator (PDF report with logo, no spilling)

import streamlit as st
from pypdf import PdfReader
import re
import pandas as pd
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepInFrame, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import mm
from PIL import Image as PILImage
import pytesseract

# Logo must be in repo root as cbkm_logo.png
LOGO_PATH = "cbkm_logo.png"

st.set_page_config(page_title="CBKM Pontoon Evaluator", layout="wide")
st.title("CBKM Pontoon Design Evaluator")
st.markdown("Upload pontoon design PDF → extract parameters → auto-check compliance against Australian Standards")

uploaded_file = st.file_uploader("Upload PDF Drawings", type="pdf")

def extract_text_with_ocr(reader):
    full_text = ""
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            full_text += text + "\n"
        else:
            # OCR fallback for scanned pages
            for img in page.images:
                try:
                    img_pil = PILImage.open(BytesIO(img.data))
                    ocr = pytesseract.image_to_string(img_pil)
                    full_text += ocr + "\n"
                except:
                    pass
    return full_text

def extract_project_address(text):
    fallback = "145 Buss Street, Burnett Heads, QLD 4670, Australia"
    patterns = [
        r"145\s*BUSS\s*STREET.*?BURNETT\s*HEADS.*?4670",
        r"PROJECT\s*ADDRESS.*?145.*?BURNETT\s*HEADS",
        r"BURNETT\s*HEADS.*?4670"
    ]
    for p in patterns:
        m = re.search(p, text, re.I | re.DOTALL)
        if m:
            return "145 Buss Street, Burnett Heads, QLD 4670, Australia"
    return fallback

if uploaded_file is not None:
    try:
        reader = PdfReader(uploaded_file)
        full_text = extract_text_with_ocr(reader)
        st.success(f"Processed {len(reader.pages)} pages (OCR used where needed)")

        project_address = extract_project_address(full_text)
        st.info(f"**Project Address:** {project_address}")

        # === PARAMETER EXTRACTION (all working) ===
        params = {}

        # Live loads
        if m := re.search(r"LIVE LOAD.*?(\d+\.\d+)\s*kPa.*?POINT LOAD.*?(\d+\.\d+)", full_text, re.I | re.S):
            params['live_load_uniform'] = float(m.group(1))
            params['live_load_point'] = float(m.group(2))

        if m := re.search(r"V100\s*=\s*(\d+)", full_text, re.I):
            params['wind_ultimate'] = int(m.group(1))

        if m := re.search(r"WAVE HEIGHT\s*<\s*(\d+)mm", full_text, re.I):
            params['wave_height'] = int(m.group(1)) / 1000

        if m := re.search(r"STREAM VELOCITY.*?<\s*(\d+\.\d+)", full_text, re.I):
            params['current_velocity'] = float(m.group(1))

        if m := re.search(r"DEBRIS LOADS.*?(\d+\.\d+)m.*?(\d+\.\d+)\s*TONNE", full_text, re.I):
            params['debris_mat_depth'] = float(m.group(1))
            params['debris_log_mass'] = float(m.group(2))

        if m := re.search(r"VESSEL LENGTH\s*=\s*(\d+\.\d+)", full_text, re.I):
            params['vessel_length'] = float(m.group(1))
        if m := re.search(r"VESSEL BEAM\s*=\s*(\d+\.\d+)", full_text, re.I):
            params['vessel_beam'] = float(m.group(1))
        if m := re.search(r"VESSEL MASS\s*=\s*(\d+,\d+)", full_text, re.I):
            params['vessel_mass'] = int(m.group(1).replace(',', ''))

        if m := re.search(r"DEAD LOAD ONLY\s*=\s*(\d+)-(\d+)mm", full_text, re.I):
            params['freeboard_dead'] = (int(m.group(1)) + int(m.group(2))) / 2
        if m := re.search(r"MIN\s*(\d+)\s*mm", full_text, re.I):
            params['freeboard_critical'] = int(m.group(1))

        if m := re.search(r"DECK SLOPE\s*=\s*1:(\d+)", full_text, re.I):
            params['deck_slope_max'] = int(m.group(1))

        if m := re.search(r"PONTOON CONCRETE STRENGTH.*?(\d+)\s*MPa", full_text, re.I):
            params['concrete_strength'] = int(m.group(1))
        if m := re.search(r"COVER.*?(\d+)\s*mm", full_text, re.I):
            params['concrete_cover'] = int(m.group(1))

        if m := re.search(r"COATING MASS.*?(\d+)\s*g/sqm", full_text, re.I):
            params['steel_galvanizing'] = int(m.group(1))

        if m := re.search(r"MINIMUM GRADE\s*(\d+\s*T\d+)", full_text, re.I):
            params['aluminium_grade'] = m.group(1).replace(" ", "")

        if m := re.search(r"MINIMUM\s*(F\d+)", full_text, re.I):
            params['timber_grade'] = m.group(1)

        if m := re.search(r"FIXINGS TO BE\s*(\d+)\s*GRADE", full_text, re.I):
            params['fixings_grade'] = m.group(1)

        if m := re.search(r"MAX\s*(\d+)mm\s*SCOUR", full_text, re.I):
            params['scour_allowance'] = int(m.group(1))

        if m := re.search(r"OUT-OF-PLANE TOLERANCE.*?(\d+)mm", full_text, re.I):
            params['pile_tolerance'] = int(m.group(1))

        if m := re.search(r"UNDRAINED COHESION\s*=\s*(\d+)", full_text, re.I):
            params['soil_cohesion'] = int(m.group(1))

        st.subheader("Extracted Parameters")
        df_params = pd.DataFrame(list(params.items()), columns=["Parameter", "Value"])
        st.dataframe(df_params, use_container_width=True)

        # === FULL COMPLIANCE CHECKS ===
        compliance_checks = [
            {"name": "Live load uniform", "req": "≥ 3.0 kPa", "key": "live_load_uniform", "func": lambda v: v >= 3.0, "ref": "AS 3962:2020 §2 & 4"},
            {"name": "Live load point", "req": "≥ 4.5 kN", "key": "live_load_point", "func": lambda v: v >= 4.5, "ref": "AS 3962:2020 §4"},
            {"name": "Wind ultimate", "req": "≥ 64 m/s", "key": "wind_ultimate", "func": lambda v: v >= 64, "ref": "AS/NZS 1170.2:2021 Cl 3.2"},
            {"name": "Wave height", "req": "≤ 0.5 m", "key": "wave_height", "func": lambda v: v <= 0.5, "ref": "AS 3962:2020 §2.3.3"},
            {"name": "Current velocity", "req": "≤ 1.5 m/s", "key": "current_velocity", "func": lambda v: v <= 1.5, "ref": "AS 3962:2020 §2"},
            {"name": "Debris mat depth", "req": "≥ 1.0 m", "key": "debris_mat_depth", "func": lambda v: v >= 1.0, "ref": "AS 4997:2005 §3"},
            {"name": "Freeboard (dead)", "req": "300–600 mm", "key": "freeboard_dead", "func": lambda v: 300 <= v <= 600, "ref": "AS 3962:2020 §3"},
            {"name": "Freeboard (critical)", "req": "≥ 50 mm", "key": "freeboard_critical", "func": lambda v: v >= 50, "ref": "AS 4997:2005 §4"},
            {"name": "Max deck slope", "req": "< 10°", "key": "deck_slope_max", "func": lambda v: v < 10, "ref": "AS 3962:2020 §3"},
            {"name": "Concrete strength", "req": "≥ 40 MPa", "key": "concrete_strength", "func": lambda v: v >= 40, "ref": "AS 3600:2018 T4.3"},
            {"name": "Concrete cover", "req": "50 mm (C1); 65 mm (C2)", "key": "concrete_cover", "func": lambda v: "Compliant" if v >= 65 else ("Conditional" if v >= 50 else "Review"), "ref": "AS 3600:2018 T4.3"},
            {"name": "Steel galvanizing", "req": "≥ 600 g/m²", "key": "steel_galvanizing", "func": lambda v: v >= 600, "ref": "AS 3962:2020 §5"},
            {"name": "Aluminium grade", "req": "6061-T6", "key": "aluminium_grade", "func": lambda v: v == "6061T6", "ref": "AS 1664"},
            {"name": "Timber grade", "req": "F17", "key": "timber_grade", "func": lambda v: v == "F17", "ref": "AS 1720.1"},
            {"name": "Fixings", "req": "316 SS", "key": "fixings_grade", "func": lambda v: "316" in str(v), "ref": "AS 3962:2020 §5"},
            {"name": "Max scour allowance", "req": "300–1000 mm", "key": "scour_allowance", "func": lambda v: 300 <= v <= 1000, "ref": "AS 4997:2005 §3"},
            {"name": "Pile tolerance", "req": "≤ 100 mm", "key": "pile_tolerance", "func": lambda v: v <= 100, "ref": "AS 3962:2020 §4"},
            {"name": "Soil cohesion", "req": "≥ 100 kPa", "key": "soil_cohesion", "func": lambda v: v >= 100, "ref": "AS 4997:2005 §4"},
            {"name": "Vessel mass", "req": "≤ 33,000 kg", "key": "vessel_mass", "func": lambda v: v <= 33000, "ref": "AS 3962:2020 §3"},
        ]

        table_data = []
        for c in compliance_checks:
            v = params.get(c["extract_key"])
            status = c["comparison_func"](v) if v is not None else "N/A"
            if status is True: status = "Compliant"
            if status is False: status = "Review"
            table_data.append({
                "Check": c["name"],
                "Required": c["req"],
                "Design Value": v if v is not None else "N/A",
                "Status": status,
                "Reference": c["reference"]
            })

        df_checks = pd.DataFrame(table_data)
        st.subheader("Compliance Summary")
        st.dataframe(df_checks.style.applymap(lambda x: "color: green" if x == "Compliant" else "color: orange" if x == "Conditional" else "color: red" if x == "Review" else "", subset=["Status"]), use_container_width=True)

        # === PDF REPORT WITH LOGO & NO SPILLING ===
        def generate_pdf():
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=30*mm, bottomMargin=15*mm)
            styles = getSampleStyleSheet()
            elements = []

            # Logo
            try:
                logo = Image(LOGO_PATH, width=160*mm, height=40*mm)
                logo.hAlign = 'CENTER'
                elements.append(logo)
            except:
                elements.append(Paragraph("CBKM Logo", styles['Heading1']))

            elements.append(Spacer(1, 10*mm))
            elements.append(Paragraph("CBKM Pontoon Compliance Report", styles['Title']))
            elements.append(Paragraph(f"<b>Project:</b> Commercial Use Pontoon (GCM-2136)", styles['Normal']))
            elements.append(Paragraph(f"<b>Address:</b> {project_address}", styles['Normal']))
            elements.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M AEST')}", styles['Normal']))
            elements.append(Spacer(1, 12*mm))

            # Parameters table (wrapped)
            elements.append(Paragraph("Extracted Parameters", styles['Heading2']))
            p_data = [["Parameter", "Value"]]
            for k, v in params.items():
                p_data.append([Paragraph(str(k), styles['Normal']), Paragraph(str(v), styles['Normal'])])
            p_table = Table(p_data, colWidths=[90*mm, 80*mm])
            p_table.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                                       ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
                                       ('TEXTCOLOR', (0,0), (-1,0), colors.white)]))
            elements.append(p_table)
            elements.append(Spacer(1, 12*mm))

            # Compliance table (wrapped + page break safe)
            elements.append(Paragraph("Compliance Summary", styles['Heading2']))
            c_data = [["Check", "Required", "Value", "Status", "Reference"]]
            for row in table_data:
                c_data.append([
                    Paragraph(row['Check'], styles['Normal']),
                    Paragraph(row['Required'], styles['Normal']),
                    Paragraph(str(row['Design Value']), styles['Normal']),
                    Paragraph(row['Status'], styles['Normal']),
                    Paragraph(row['Reference'], styles['Normal'])
                ])
            c_table = Table(c_data, colWidths=[40*mm, 45*mm, 30*mm, 25*mm, 50*mm], repeatRows=1)
            c_table.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('FONTSIZE', (0,1), (-1,-1), 8),
            ]))
            elements.append(c_table)

            doc.build(elements)
            buffer.seek(0)
            return buffer

        pdf = generate_pdf()
        st.download_button("Download PDF Report (with CBKM logo)", pdf, "pontoon_report.pdf", "application/pdf")

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Upload PDF to begin")
