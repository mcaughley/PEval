# app.py - FINAL: Project address dynamic + default blank, footer on title page only, Non-Compliant + Project Risk on last page

import streamlit as st
from pypdf import PdfReader
import re
import pandas as pd
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import mm

# Logo (must be in repo root)
LOGO_PATH = "cbkm_logo.png"

st.set_page_config(page_title="CBKM Pontoon Evaluator", layout="wide")

st.title("CBKM Pontoon Design Evaluator")
st.markdown("Upload pontoon design PDF → extract parameters → auto-check compliance against Australian Standards")

# Sidebar for editable footer (title page only)
with st.sidebar:
    st.header("PDF Report Footer (Title Page Only)")
    engineer_name = st.text_input("Engineer Name", "Matt McAughley")
    rpeq_number = st.text_input("RPEQ Number", "RPEQ XXXXXX (Certification Pending)")
    company_name = st.text_input("Company", "CBKM Consulting Pty Ltd")
    company_contact = st.text_input("Contact", "info@cbkm.au | Brisbane, QLD")
    signature_note = st.text_input("Signature Line", "Signed: ______________________________")

uploaded_file = st.file_uploader("Upload PDF Drawings", type="pdf")

def extract_project_address(text):
    # Default is now blank (empty string)
    fallback = ""

    # Remove common prefixes/noise
    text = re.sub(r"(PROJECT\s*(?:ADDRESS|USE ADDRESS|NEW COMMERCIAL USE PONTOON|PONTOON|PROPOSED|USE)?\s*:\s*)", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()

    # Match core address pattern (case-insensitive, flexible spacing)
    if re.search(r"145\s*BUSS\s*STREET.*BURNETT\s*HEADS.*4670", text, re.I | re.DOTALL):
        return "145 Buss Street, Burnett Heads, QLD 4670, Australia"

    return fallback  # blank if no match

if uploaded_file is not None:
    try:
        reader = PdfReader(uploaded_file)
        full_text = ""
        for page in reader.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"

        st.success(f"PDF processed ({len(reader.pages)} pages)")

        project_address = extract_project_address(full_text)
        st.info(f"**Project Address:** {project_address if project_address else '(Not detected in PDF)'}")

        # Parameter extraction (flexible regex)
        params = {}

        if m := re.search(r"LIVE LOAD.*?(\d+\.\d+)\s*kPa.*?POINT LOAD.*?(\d+\.\d+)\s*kN", full_text, re.I | re.DOTALL):
            params['live_load_uniform'] = float(m.group(1))
            params['live_load_point'] = float(m.group(2))

        if m := re.search(r"V100\s*=\s*(\d+)\s*m/s", full_text, re.I | re.DOTALL):
            params['wind_ultimate'] = int(m.group(1))

        if m := re.search(r"WAVE HEIGHT\s*<\s*(\d+)\s*mm", full_text, re.I | re.DOTALL):
            params['wave_height'] = int(m.group(1)) / 1000.0

        if m := re.search(r"VELOCITY.*?<\s*(\d+\.\d+)\s*m/s", full_text, re.I | re.DOTALL):
            params['current_velocity'] = float(m.group(1))

        if m := re.search(r"DEBRIS LOADS.*?(\d+\.\d+)\s*m.*?(\d+\.\d+)\s*TONNE", full_text, re.I | re.DOTALL):
            params['debris_mat_depth'] = float(m.group(1))
            params['debris_log_mass'] = float(m.group(2))

        if m := re.search(r"LENGTH\s*=\s*(\d+\.\d+)\s*m", full_text, re.I | re.DOTALL):
            params['vessel_length'] = float(m.group(1))
        if m := re.search(r"BEAM\s*=\s*(\d+\.\d+)\s*m", full_text, re.I | re.DOTALL):
            params['vessel_beam'] = float(m.group(1))
        if m := re.search(r"MASS\s*=\s*(\d+,\d+)\s*kg", full_text, re.I | re.DOTALL):
            params['vessel_mass'] = int(m.group(1).replace(',', ''))

        if m := re.search(r"DEAD LOAD ONLY\s*=\s*(\d+)-(\d+)mm", full_text, re.I | re.DOTALL):
            params['freeboard_dead'] = (int(m.group(1)) + int(m.group(2))) / 2
        if m := re.search(r"MIN\s*(\d+)\s*mm", full_text, re.I | re.DOTALL):
            params['freeboard_critical'] = int(m.group(1))

        if m := re.search(r"DECK SLOPE\s*=\s*1:(\d+)", full_text, re.I | re.DOTALL):
            params['deck_slope_max'] = int(m.group(1))

        if m := re.search(r"PONTOON CONCRETE.*?(\d+)\s*MPa", full_text, re.I | re.DOTALL):
            params['concrete_strength'] = int(m.group(1))
        if m := re.search(r"COVER.*?(\d+)\s*mm", full_text, re.I | re.DOTALL):
            params['concrete_cover'] = int(m.group(1))

        if m := re.search(r"COATING MASS.*?(\d+)\s*g/sqm", full_text, re.I | re.DOTALL):
            params['steel_galvanizing'] = int(m.group(1))

        if m := re.search(r"MINIMUM GRADE\s*(\d+\s*T\d+)", full_text, re.I | re.DOTALL):
            params['aluminium_grade'] = m.group(1).replace(" ", "")

        if m := re.search(r"MINIMUM\s*(F\d+)", full_text, re.I | re.DOTALL):
            params['timber_grade'] = m.group(1)

        if m := re.search(r"FIXINGS TO BE\s*(\d+)\s*GRADE", full_text, re.I | re.DOTALL):
            params['fixings_grade'] = m.group(1)

        if m := re.search(r"MAX\s*(\d+)mm\s*SCOUR", full_text, re.I | re.DOTALL):
            params['scour_allowance'] = int(m.group(1))

        if m := re.search(r"TOLERANCE.*?(\d+)mm", full_text, re.I | re.DOTALL):
            params['pile_tolerance'] = int(m.group(1))

        if m := re.search(r"COHESION\s*=\s*(\d+)kPa", full_text, re.I | re.DOTALL):
            params['soil_cohesion'] = int(m.group(1))

        st.subheader("Extracted Parameters")
        if params:
            df_params = pd.DataFrame(list(params.items()), columns=["Parameter", "Value"])
            df_params["Value"] = df_params["Value"].astype(str)  # Fix Arrow type error
            st.dataframe(df_params, width='stretch')
        else:
            st.warning("No parameters extracted – try a different PDF or check OCR.")

        # Full compliance checks
        compliance_checks = [
            {"name": "Live load uniform", "req": "≥ 3.0 kPa", "key": "live_load_uniform", "func": lambda v: v >= 3.0 if v is not None else False, "ref": "AS 3962:2020 §2 & 4"},
            {"name": "Live load point", "req": "≥ 4.5 kN", "key": "live_load_point", "func": lambda v: v >= 4.5 if v is not None else False, "ref": "AS 3962:2020 §4"},
            {"name": "Wind ultimate", "req": "≥ 64 m/s", "key": "wind_ultimate", "func": lambda v: v >= 64 if v is not None else False, "ref": "AS/NZS 1170.2:2021 Cl 3.2"},
            {"name": "Wave height", "req": "≤ 0.5 m", "key": "wave_height", "func": lambda v: v <= 0.5 if v is not None else False, "ref": "AS 3962:2020 §2.3.3"},
            {"name": "Current velocity", "req": "≤ 1.5 m/s", "key": "current_velocity", "func": lambda v: v <= 1.5 if v is not None else False, "ref": "AS 3962:2020 §2"},
            {"name": "Debris mat depth", "req": "≥ 1.0 m", "key": "debris_mat_depth", "func": lambda v: v >= 1.0 if v is not None else False, "ref": "AS 4997:2005 §3"},
            {"name": "Freeboard (dead)", "req": "300–600 mm", "key": "freeboard_dead", "func": lambda v: 300 <= v <= 600 if v is not None else False, "ref": "AS 3962:2020 §3"},
            {"name": "Freeboard (critical)", "req": "≥ 50 mm", "key": "freeboard_critical", "func": lambda v: v >= 50 if v is not None else False, "ref": "AS 4997:2005 §4"},
            {"name": "Max deck slope", "req": "< 10°", "key": "deck_slope_max", "func": lambda v: v < 10 if v is not None else False, "ref": "AS 3962:2020 §3"},
            {"name": "Concrete strength", "req": "≥ 40 MPa", "key": "concrete_strength", "func": lambda v: v >= 40 if v is not None else False, "ref": "AS 3600:2018 T4.3"},
            {"name": "Concrete cover", "req": "50 mm (C1); 65 mm (C2)", "key": "concrete_cover", "func": lambda v: "Compliant" if v >= 65 else ("Conditional" if v >= 50 else "Review") if v is not None else "N/A", "ref": "AS 3600:2018 T4.3"},
            {"name": "Steel galvanizing", "req": "≥ 600 g/m²", "key": "steel_galvanizing", "func": lambda v: v >= 600 if v is not None else False, "ref": "AS 3962:2020 §5"},
            {"name": "Aluminium grade", "req": "6061-T6", "key": "aluminium_grade", "func": lambda v: v == "6061T6" if v is not None else False, "ref": "AS 1664"},
            {"name": "Timber grade", "req": "F17", "key": "timber_grade", "func": lambda v: v == "F17" if v is not None else False, "ref": "AS 1720.1"},
            {"name": "Fixings", "req": "316 SS", "key": "fixings_grade", "func": lambda v: "316" in str(v) if v is not None else False, "ref": "AS 3962:2020 §5"},
            {"name": "Max scour allowance", "req": "300–1000 mm", "key": "scour_allowance", "func": lambda v: 300 <= v <= 1000 if v is not None else False, "ref": "AS 4997:2005 §3"},
            {"name": "Pile tolerance", "req": "≤ 100 mm", "key": "pile_tolerance", "func": lambda v: v <= 100 if v is not None else False, "ref": "AS 3962:2020 §4"},
            {"name": "Soil cohesion", "req": "≥ 100 kPa", "key": "soil_cohesion", "func": lambda v: v >= 100 if v is not None else False, "ref": "AS 4997:2005 §4"},
            {"name": "Vessel mass", "req": "≤ 33,000 kg", "key": "vessel_mass", "func": lambda v: v <= 33000 if v is not None else False, "ref": "AS 3962:2020 §3"},
        ]

        table_data = []
        for c in compliance_checks:
            v = params.get(c["key"])
            status = "Compliant" if c["func"](v) is True else ("Review" if c["func"](v) is False else c["func"](v) if isinstance(c["func"](v), str) else "N/A")
            table_data.append({
                "Check": c["name"],
                "Required": c["req"],
                "Design Value": v if v is not None else "N/A",
                "Status": status,
                "Reference": c["ref"]
            })

        df_checks = pd.DataFrame(table_data)
        st.subheader("Compliance Summary")
        st.dataframe(df_checks.style.applymap(lambda x: "color: green" if x == "Compliant" else "color: orange" if x == "Conditional" else "color: red" if x == "Review" else "", subset=["Status"]), width='stretch')

        # PDF Report with elegant title page + footer on title page only
        def generate_pdf():
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=15*mm,
                leftMargin=15*mm,
                topMargin=20*mm,
                bottomMargin=50*mm
            )
            styles = getSampleStyleSheet()
            elements = []

            # === ELEGANT TITLE PAGE (logo + details + footer) ===
            try:
                logo = Image(LOGO_PATH, width=180*mm, height=60*mm)
                logo.hAlign = 'CENTER'
                elements.append(logo)
            except:
                elements.append(Paragraph("CBKM Logo", styles['Heading1']))

            elements.append(Spacer(1, 50*mm))

            title_style = styles['Title']
            title_style.fontSize = 28
            title_style.alignment = 1
            elements.append(Paragraph("CBKM Pontoon Compliance Report", title_style))

            elements.append(Spacer(1, 20*mm))

            elements.append(Paragraph("Commercial Use Pontoon (GCM-2136)", styles['Heading2']))
            elements.append(Spacer(1, 8*mm))
            elements.append(Paragraph(project_address if project_address else "Not detected", styles['Heading3']))
            elements.append(Spacer(1, 8*mm))
            elements.append(Paragraph(datetime.now().strftime('%Y-%m-%d %H:%M AEST'), styles['Heading3']))

            # Footer table on title page only
            footer_data = [
                ["Prepared by:", engineer_name],
                ["RPEQ Number:", rpeq_number],
                ["Date:", datetime.now().strftime('%d %B %Y')],
                ["Signature:", signature_note],
                ["Company:", company_name],
                ["Contact:", company_contact]
            ]
            footer_table = Table(footer_data, colWidths=[50*mm, 130*mm])
            footer_table.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ('ALIGN', (0,0), (0,-1), 'RIGHT'),
                ('ALIGN', (1,0), (1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('FONTSIZE', (0,0), (-1,-1), 9),
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
                ('TEXTCOLOR', (0,0), (0,-1), colors.darkblue),
                ('BOX', (0,0), (-1,-1), 1, colors.black),
            ]))
            elements.append(Spacer(1, 40*mm))
            elements.append(footer_table)

            elements.append(PageBreak())  # Parameters on next page

            # Parameters table (separate page)
            elements.append(Paragraph("Extracted Parameters from Drawings", styles['Heading2']))
            p_data = [["Parameter", "Value"]]
            for k, v in params.items():
                p_data.append([Paragraph(str(k), styles['Normal']), Paragraph(str(v), styles['Normal'])])
            p_table = Table(p_data, colWidths=[90*mm, 90*mm])
            p_table.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            elements.append(p_table)
            elements.append(PageBreak())  # Compliance on next page

            # Compliance table (separate page)
            elements.append(Paragraph("Compliance Summary (Standards-Based)", styles['Heading2']))
            c_data = [["Check", "Required", "Design Value", "Status"]]
            for row in table_data:
                c_data.append([
                    Paragraph(row['Check'], styles['Normal']),
                    Paragraph(row['Required'], styles['Normal']),
                    Paragraph(str(row['Design Value']), styles['Normal']),
                    Paragraph(row['Status'], styles['Normal'])
                ])
            c_table = Table(c_data, colWidths=[60*mm, 50*mm, 40*mm, 30*mm], repeatRows=1)
            c_table.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('ALIGN', (0,0), (-1,0), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('FONTSIZE', (0,1), (-1,-1), 9),
                ('BACKGROUND', (0,1), (-1,-1), colors.lightgrey),
            ]))
            elements.append(c_table)
            elements.append(PageBreak())  # Non-compliant + Project Risk on last page

            # Non-Compliant Items Risk (on last page)
            non_compliant = [row for row in table_data if row["Status"] in ["Review", "Conditional"]]
            if non_compliant:
                elements.append(Paragraph("Non-Compliant Items Risk", styles['Heading2']))
                nc_data = [["Check", "Required", "Design Value", "Status"]]
                for row in non_compliant:
                    nc_data.append([
                        Paragraph(row['Check'], styles['Normal']),
                        Paragraph(row['Required'], styles['Normal']),
                        Paragraph(str(row['Design Value']), styles['Normal']),
                        Paragraph(row['Status'], styles['Normal'])
                    ])
                nc_table = Table(nc_data, colWidths=[60*mm, 50*mm, 40*mm, 30*mm])
                nc_table.setStyle(TableStyle([
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                    ('BACKGROUND', (0,0), (-1,0), colors.red),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                    ('ALIGN', (0,0), (-1,0), 'CENTER'),
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('FONTSIZE', (0,1), (-1,-1), 9),
                    ('BACKGROUND', (0,1), (-1,-1), colors.lightgrey),
                ]))
                elements.append(nc_table)
                elements.append(Spacer(1, 12*mm))  # Gap before Project Risk

            # Project Risk section (below non-compliant, on same last page)
            elements.append(Paragraph("Project Risk", styles['Heading2']))
            elements.append(Spacer(1, 12*mm))
            # Add ~10 lines of free space
            for _ in range(10):
                elements.append(Spacer(1, 12*mm))  # Approx 10 blank lines

            # Build PDF (no footer on later pages)
            doc.build(elements)
            buffer.seek(0)
            return buffer

        pdf_buffer = generate_pdf()
        st.download_button(
            label="Download Report (Footer on Title Page Only)",
            data=pdf_buffer,
            file_name="pontoon_compliance_report.pdf",
            mime="application/pdf"
        )

    except Exception as e:
        st.error(f"Error: {str(e)}")

else:
    st.info("Upload PDF to begin.")
