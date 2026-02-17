import streamlit as st
from pypdf import PdfReader
import re
import pandas as pd
from datetime import datetime
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter

st.set_page_config(page_title="CBKM Pontoon Evaluator", layout="wide")
st.title("CBKM Pontoon Design Evaluator")

st.markdown("""
Upload pontoon design PDF drawings → extract engineering parameters → 
evaluate compliance against relevant Australian Standards.

**References:** AS 3962:2020, AS 4997:2005, AS/NZS 1170.2:2021, AS 3600:2018, QLD Tidal Works.
""")

uploaded_file = st.file_uploader("📄 Upload Pontoon PDF Drawings", type="pdf")

def extract_text_from_pdf(pdf_bytes):
    reader = PdfReader(BytesIO(pdf_bytes))
    all_text = ""
    for page in reader.pages:
        text = page.extract_text() or ""
        all_text += text + "\n"
    return re.sub(r"\s+", " ", all_text)

def extract_project_address(txt):
    fallback = "145 Buss Street, Burnett Heads, QLD 4670, Australia"
    patterns = [
        r"PROJECT\s*ADDRESS[:\s]*(.*?QLD\s*\d{4})",
        r"LOCATION[:\s]*(.*?QLD\s*\d{4})",
        r"(145\s*BUSS\s*STREET.*?BURNETT\s*HEADS.*?QLD\s*\d{4})",
    ]
    for p in patterns:
        m = re.search(p, txt, re.I)
        if m:
            return m.group(1).strip()
    return fallback

def safe_float(pat, txt, default=0.0):
    m = re.search(pat, txt, re.I)
    if m:
        try:
            return float(m.group(1))
        except:
            return default
    return default

def safe_int(pat, txt, default=0):
    m = re.search(pat, txt, re.I)
    if m:
        try:
            return int(m.group(1))
        except:
            return default
    return default

if uploaded_file:
    try:
        data = uploaded_file.read()
        full_text = extract_text_from_pdf(data)
        
        with st.expander("🔍 View Extracted Text"):
            st.text_area("Raw text", full_text[:10000], height=200)

        addr = extract_project_address(full_text)
        project_address = st.text_input("📍 Project Address", addr)

        params = {}
        
        conc = safe_int(r"CONCRETE\s*(?:STRENGTH|GRADE)[^\d]*([3-9][0-9])\s*MPa", full_text)
        if conc:
            params["Concrete Strength"] = f"{conc} MPa"
        
        rebar = re.search(r"REBAR\s*GRADE[^\w]*([A-Z0-9]+)", full_text, re.I)
        params["Rebar Grade"] = rebar.group(1) if rebar else "N/A"
        
        cover = safe_int(r"COVER[^\d]*([0-9]+)\s*mm", full_text)
        if cover:
            params["Concrete Cover"] = f"{cover} mm"
        
        galv = safe_int(r"GALVANIZ[^\d]*([0-9]+)", full_text)
        if galv:
            params["Galvanizing"] = f"{galv} g/m²"
        
        timber = re.search(r"(F\d+)", full_text)
        params["Timber Grade"] = timber.group(1) if timber else "N/A"
        
        wind = safe_int(r"WIND\s*SPEED[^\d]*([0-9]{2})", full_text)
        if wind:
            params["Wind Speed V100"] = f"{wind} m/s"
        
        live_u = safe_float(r"LIVE\s*LOAD[^\d]*([0-9]+(?:\.[0-9]+)?)\s*kPa", full_text)
        if live_u:
            params["Live Load Uniform"] = f"{live_u} kPa"
        
        live_p = safe_float(r"POINT\s*LOAD[^\d]*([0-9]+(?:\.[0-9]+)?)\s*kN", full_text)
        if live_p:
            params["Live Load Point"] = f"{live_p} kN"

        st.subheader("📋 Extracted Parameters")
        if params:
            df_params = pd.DataFrame([{"Parameter": k, "Value": v} for k, v in params.items()])
            st.dataframe(df_params, use_container_width=True)
        else:
            st.warning("No parameters extracted")

        checks = []
        
        if conc:
            status = "Compliant" if conc >= 40 else "Review"
            checks.append({
                "Check": "Concrete Strength",
                "Requirement": "≥ 40 MPa",
                "Design Value": f"{conc} MPa",
                "Status": status,
                "Reference": "AS 3600:2018"
            })
        
        if wind:
            status = "Compliant" if wind >= 57 else "Review"
            checks.append({
                "Check": "Wind Speed V100",
                "Requirement": "≥ 57 m/s",
                "Design Value": f"{wind} m/s",
                "Status": status,
                "Reference": "AS/NZS 1170.2"
            })
        
        if cover:
            status = "Compliant" if cover >= 50 else "Review"
            checks.append({
                "Check": "Concrete Cover",
                "Requirement": "≥ 50 mm",
                "Design Value": f"{cover} mm",
                "Status": status,
                "Reference": "AS 3600:2018"
            })

        st.subheader("✅ Compliance Review")
        if checks:
            df_checks = pd.DataFrame(checks)
            st.dataframe(df_checks, use_container_width=True)
        else:
            st.info("No compliance checks available")

        st.sidebar.header("Report Information")
        engineer = st.sidebar.text_input("Engineer Name", "Matt Caughley")
        rpeq = st.sidebar.text_input("RPEQ", "")
        company = st.sidebar.text_input("Company", "CBKM Engineering")
        contact = st.sidebar.text_input("Contact", "Email/Phone")

        if st.button("📘 Generate PDF Report"):
            buf = BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=letter)
            s = getSampleStyleSheet()
            els = []
            
            els.append(Paragraph("CBKM Pontoon Evaluation Report", s["Title"]))
            els.append(Paragraph(datetime.now().strftime("%B %d, %Y"), s["Normal"]))
            els.append(Paragraph(f"Project: {project_address}", s["Normal"]))
            els.append(Spacer(1, 12))
            
            if params:
                pdata = [["Parameter", "Value"]] + [[k, v] for k, v in params.items()]
                t1 = Table(pdata)
                t1.setStyle(TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke)
                ]))
                els.append(t1)
                els.append(Spacer(1, 12))
            
            if checks:
                cdata = [["Check", "Requirement", "Design Value", "Status", "Reference"]]
                cdata += [[c["Check"], c["Requirement"], c["Design Value"], c["Status"], c["Reference"]] for c in checks]
                t2 = Table(cdata)
                t2.setStyle(TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke)
                ]))
                els.append(t2)
                els.append(Spacer(1, 12))
            
            els.append(Paragraph("Summary: Automated compliance screening per Australian Standards.", s["Normal"]))
            els.append(Spacer(1, 12))
            els.append(Paragraph(f"Engineer: {engineer} {rpeq}", s["Normal"]))
            els.append(Paragraph(f"Company: {company}", s["Normal"]))
            els.append(Paragraph(f"Contact: {contact}", s["Normal"]))
            
            doc.build(els)
            buf.seek(0)
            st.download_button("⬇️ Download Report", buf, "pontoon_evaluation_report.pdf", "application/pdf")

    except Exception as e:
        st.error(f"Error: {e}")
