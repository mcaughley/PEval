python
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

LOGO_PATH = "cbkm_logo.png"

st.set_page_config(page_title="CBKM Pontoon Evaluator", layout="wide")
st.title("CBKM Pontoon Design Evaluator")
st.markdown("Upload pontoon design PDF → extract parameters → auto-check compliance")

with st.sidebar:
    st.header("PDF Report Footer (Title Page Only)")
    engineer_name = st.text_input("Engineer Name", "Matthew Caughley")
    rpeq_number = st.text_input("RPEQ Number", "25332")
    company_name = st.text_input("Company", "CBKM Consulting Pty Ltd")
    company_contact = st.text_input("Contact", "mcaughley@cbkm.au | 0434 173 808")
    signature_note = st.text_input("Signature Line", "")

uploaded_file = st.file_uploader("Upload PDF Drawings", type="pdf")

def extract_project_address(text):
    if m := re.search(r"PROJECT\s*(?:ADDRESS|USE ADDRESS|NEW COMMERCIAL USE PONTOON|PONTOON)?\s*:\s*(.+)", text, re.I):
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return ""

if uploaded_file is not None:
    try:
        reader = PdfReader(uploaded_file)
        full_text = ""
        for page in reader.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"

        st.success(f"PDF processed ({len(reader.pages)} pages)")

        st.text_area("Extracted Full Text (Debug)", full_text, height=300)

        project_address = extract_project_address(full_text)
        st.info(f"**Project Address:** {project_address if project_address else '(Not detected in PDF)'}")

        params = {}

        if m := re.search(r"live\s*load\s*(uniform)?\s*[:=]?\s*(\d+\.?\d*)\s*kPa", full_text, re.I | re.DOTALL):
            params['live_load_uniform'] = float(m.group(2))
        if m := re.search(r"(point|concentrated)\s*load\s*[:=]?\s*(\d+\.?\d*)\s*kN", full_text, re.I | re.DOTALL):
            params['live_load_point'] = float(m.group(2))
        if m := re.search(r"(V100|ultimate\s*wind\s*(speed|velocity))\s*=\s*(\d+)\s*m/s", full_text, re.I | re.DOTALL):
            params['wind_ultimate'] = int(m.group(3))
        if m := re.search(r"wave\s*height\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(m|mm)", full_text, re.I | re.DOTALL):
            value = float(m.group(1))
            params['wave_height'] = value if m.group(2).lower() == 'm' else value / 1000.0
        if m := re.search(r"(current|velocity)\s*[:=]?\s*(\d+\.?\d*)\s*m/s", full_text, re.I | re.DOTALL):
            params['current_velocity'] = float(m.group(2))
        if m := re.search(r"debris\s*(mat\s*(depth|thickness)?)\s*[:=]?\s*(\d+\.?\d*)\s*m", full_text, re.I | re.DOTALL):
            params['debris_mat_depth'] = float(m.group(3))
        if m := re.search(r"vessel\s*length\s*[:=]?\s*(\d+\.?\d*)\s*m", full_text, re.I | re.DOTALL):
            params['vessel_length'] = float(m.group(1))
        if m := re.search(r"vessel\s*beam\s*[:=]?\s*(\d+\.?\d*)\s*m", full_text, re.I | re.DOTALL):
            params['vessel_beam'] = float(m.group(1))
        if m := re.search(r"vessel\s*mass\s*[:=]?\s*(\d{1,3}(?:,\d{3})*)\s*kg", full_text, re.I | re.DOTALL):
            params['vessel_mass'] = int(m.group(1).replace(',', ''))
        if m := re.search(r"(dead\s*load\s*(only)?|freeboard\s*under\s*dead\s*load)\s*[:=]?\s*(\d+)-(\d+)\s*mm", full_text, re.I | re.DOTALL):
            params['freeboard_dead'] = (int(m.group(3)) + int(m.group(4))) / 2
        if m := re.search(r"min(imum)?\s*(freeboard|critical\s*freeboard)?\s*[:=]?\s*(\d+)\s*mm", full_text, re.I | re.DOTALL):
            params['freeboard_critical'] = int(m.group(3))
        if m := re.search(r"(deck|gangway|max(imum)?)\s*slope\s*[:=]?\s*1:(\d+)", full_text, re.I | re.DOTALL):
            params['deck_slope_max'] = int(m.group(3))
        if m := re.search(r"concrete\s*(strength)?\s*[:=]?\s*(\d+)\s*MPa", full_text, re.I | re.DOTALL):
            params['concrete_strength'] = int(m.group(2))
        if m := re.search(r"concrete\s*cover\s*[:=]?\s*(\d+)\s*mm", full_text, re.I | re.DOTALL):
            params['concrete_cover'] = int(m.group(1))
        if m := re.search(r"(coating|galvanizing)\s*mass\s*[:=]?\s*(\d+)\s*g/(sqm|m2)", full_text, re.I | re.DOTALL):
            params['steel_galvanizing'] = int(m.group(2))

        st.subheader("Extracted Parameters")
        if params:
            df_params = pd.DataFrame(list(params.items()), columns=["Parameter", "Value"])
            df_params["Value"] = df_params["Value"].astype(str)
            st.dataframe(df_params, use_container_width=True)

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
            {"name": "Concrete cover", "req": "50 mm (C1); 65 mm (C2)", "key": "concrete_cover", "func": lambda v: ("Compliant" if v >= 65 else "Conditional" if v >= 50 else "Review") if v is not None else "N/A", "ref": "AS 3600:2018 T4.3"},
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
        df_checks["Design Value"] = df_checks["Design Value"].astype(str)

        st.subheader("Compliance Summary")
        st.dataframe(df_checks.style.map(lambda x: "color: green" if x == "Compliant" else "color: orange" if x == "Conditional" else "color: red" if x == "Review" else "", subset=["Status"]), use_container_width=True)

        non_compliant = [row for row in table_data if row["Status"] in ["Review", "Conditional"]]
        non_compliant_count = len(non_compliant)
        risk_level = "Low" if non_compliant_count <= 5 else ("Medium" if non_compliant_count <= 9 else "High")

        summary_text = f"""
         This pontoon design has been reviewed against the relevant Australian Standards, state legislation, and LGA convenants.
            Overall project risk level: **{risk_level}**.
            - Total items checked: {len(table_data)}
            - Compliant: {len(table_data) - non_compliant_count}
            - Conditional: {len([r for r in table_data if r["Status"] == "Conditional"])}
            - Review items: {len([r for r in table_data if r["Status"] == "Review"])}
           """

        def generate_pdf():
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=20*mm, bottomMargin=50*mm)
            styles = getSampleStyleSheet()
            elements = []

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

            footer_data = [
                ["Prepared by:", engineer_name],
                ["RPEQ Number:", rpeq_number],
                ["Date:", datetime.now().strftime('%d %B %Y')],
                ["Signature:", signature_note],
                ["Company:", company_name],
                ["Contact:", company_contact]
            ]
            footer_table = Table(footer_data, colWidths=[50*mm, 130*mm])
            footer_table.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('ALIGN', (0,0), (0,-1), 'RIGHT'), ('ALIGN', (1,0), (1,-1), 'LEFT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('FONTSIZE', (0,0), (-1,-1), 9), ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'), ('BACKGROUND', (0,0), (0,-1), colors.lightgrey), ('TEXTCOLOR', (0,0), (0,-1), colors.darkblue), ('BOX', (0,0), (-1,-1), 1, colors.black)]))
            elements.append(Spacer(1, 40*mm))
            elements.append(footer_table)

            elements.append(PageBreak())

            elements.append(Paragraph("Extracted Parameters from Drawings", styles['Heading2']))
            p_data = [["Parameter", "Value"]]
            for k, v in params.items():
                p_data.append([Paragraph(str(k), styles['Normal']), Paragraph(str(v), styles['Normal'])])
            p_table = Table(p_data, colWidths=[90*mm, 90*mm])
            p_table.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,0), (-1,0), colors.darkblue), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
            elements.append(p_table)
            elements.append(PageBreak())

            elements.append(Paragraph("Compliance Summary (Standards-Based)", styles['Heading2']))
            c_data = [["Check", "Required", "Design Value", "Status", "Reference"]]
            for row in table_data:
                c_data.append([Paragraph(row['Check'], styles['Normal']), Paragraph(row['Required'], styles['Normal']), Paragraph(str(row['Design Value']), styles['Normal']), Paragraph(row['Status'], styles['Normal']), Paragraph(row['Reference'], styles['Normal'])])
            c_table = Table(c_data, colWidths=[50*mm, 40*mm, 35*mm, 30*mm, 45*mm], repeatRows=1)
            c_table.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,0), (-1,0), colors.darkblue), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('ALIGN', (0,0), (-1,0), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'TOP'), ('FONTSIZE', (0,1), (-1,-1), 9), ('BACKGROUND', (0,1), (-1,-1), colors.lightgrey), ('ALIGN', (4,1), (4,-1), 'LEFT')]))
            elements.append(c_table)
            elements.append(PageBreak())

            elements.append(Paragraph("Project Risk Assessment", styles['Heading2']))
            elements.append(Spacer(1, 12*mm))

            if non_compliant:
                nc_data = [["Check", "Required", "Design Value", "Status"]]
                for row in non_compliant:
                    nc_data.append([Paragraph(row['Check'], styles['Normal']), Paragraph(row['Required'], styles['Normal']), Paragraph(str(row['Design Value']), styles['Normal']), Paragraph(row['Status'], styles['Normal'])])
                nc_table = Table(nc_data, colWidths=[60*mm, 50*mm, 40*mm, 30*mm])
                nc_table.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,0), (-1,0), colors.red), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('ALIGN', (0,0), (-1,0), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'TOP'), ('FONTSIZE', (0,1), (-1,-1), 9), ('BACKGROUND', (0,1), (-1,-1), colors.lightgrey)]))
                elements.append(nc_table)
                elements.append(Spacer(1, 12*mm))

            for line in summary_text.split('\n'):
                if line.strip():
                    elements.append(Paragraph(line, styles['Normal']))
                    elements.append(Spacer(1, 6*mm))

            for _ in range(10):
                elements.append(Spacer(1, 12*mm))

            doc.build(elements)
            buffer.seek(0)
            return buffer

        pdf_buffer = generate_pdf()
        st.download_button("Download Compliance Report", data=pdf_buffer, file_name="pontoon_compliance_report.pdf", mime="application/pdf")

        if st.button("Generate Form 12 (Aspect Inspection Certificate)"):
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = []
            elements.append(Paragraph("Form 12 - Aspect Inspection Certificate", styles['Heading1']))
            elements.append(Spacer(1, 20))
            elements.append(Paragraph(f"1. Aspect: Pontoon Concrete Construction", styles['Normal']))
            elements.append(Paragraph(f"2. Property: {project_address or 'Not detected'}", styles['Normal']))
            elements.append(Paragraph(f"8. Appointed Person: {engineer_name} (RPEQ {rpeq_number})", styles['Normal']))
            elements.append(Paragraph("9. Signature: ________________________ Date: __________", styles['Normal']))
            doc.build(elements)
            buffer.seek(0)
            st.download_button("Download Form 12", data=buffer, file_name="Form_12.pdf", mime="application/pdf")

    except Exception as e:
        st.error(f"Error: {str(e)}")

else:
    st.info("Upload PDF to begin.")
```
