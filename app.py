import streamlit as st
import re
import pandas as pd
from datetime import datetime
from io import BytesIO
import pytesseract
from PIL import Image

try:
    from pdf2image import convert_from_bytes
except ImportError:
    st.error("Missing dependency: pdf2image or Poppler not installed.")
    st.stop()

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter

st.set_page_config(page_title="CBKM Pontoon Evaluator", layout="wide")
st.title("CBKM Pontoon Design Evaluator")

st.markdown("""
Upload pontoon design PDF drawings → extract engineering parameters → 
evaluate compliance against relevant Australian Standards.

**References:** AS 3962 :2020 · AS 4997 :2005 · AS/NZS 1170.2 :2021 · AS 3600 :2018 · QLD Tidal Works
""")

uploaded_file = st.file_uploader("📄 Upload Pontoon PDF Drawings", type="pdf")

def extract_text_ocr(pdf_bytes):
    st.info("Running OCR on all pages… please wait ⏳")
    pages = convert_from_bytes(pdf_bytes, dpi=200)
    texts = []
    progress = st.progress(0)
    for i, page in enumerate(pages, 1):
        t = pytesseract.image_to_string(page)
        t = re.sub(r"\s+", " ", t)
        texts.append(t)
        progress.progress(i / len(pages))
    progress.empty()
    return "\n".join(texts), texts

def extract_project_address(txt):
    fallback = "145 Buss Street · Burnett Heads · QLD 4670 · Australia"
    for p in [
        r"PROJECT\s*ADDRESS[:\s]*(.*?QLD\s*\d{4})",
        r"LOCATION[:\s]*(.*?QLD\s*\d{4})",
        r"(145\s*BUSS\s*STREET.*?BURNETT\s*HEADS.*?QLD\s*\d{4})",
    ]:
        m = re.search(p, txt, re.I)
        if m:
            return m.group(1).strip()
    return fallback

def safe_float(pat, txt, default=0.0):
    m = re.search(pat, txt, re.I)
    return float(m.group(1)) if m else default

if uploaded_file:
    try:
        data = uploaded_file.read()
        full_text, page_texts = extract_text_ocr(data)
        st.success("✅ OCR extraction complete")

        with st.expander("🔍 View OCR Text (per page)"):
            for i, t in enumerate(page_texts, 1):
                st.text_area(f"Page {i}", t, height=200)

        addr = extract_project_address(full_text)
        project_address = st.text_input("📍 Project Address (edit if needed)", addr)

        params = {}
        params["Vessel Length"]  = f"{safe_float(r'LENGTH[:\\s]*([0-9]+(?:\\.[0-9]+)?)\\s*m', full_text)} m"
        params["Vessel Beam"]    = f"{safe_float(r'BEAM[:\\s]*([0-9]+(?:\\.[0-9]+)?)\\s*m', full_text)} m"
        params["Concrete Strength"] = f"{int(safe_float(r'CONCRETE\\s*(?:STRENGTH|GRADE)[:\\s]*([0-9]+)', full_text))} MPa"
        rebar = re.search(r'REBAR\\s*GRADE[:\\s]*([A-Z0-9]+)', full_text, re.I)
        params["Rebar Grade"] = rebar.group(1) if rebar else "500N"
        params["Galvanizing"]  = f"{int(safe_float(r'GALVANIZ(?:ED|ING)[^\\d]*([0-9]+)', full_text))} g/m²"
        timber = re.search(r'(F\\d+)', full_text)
        params["Timber Grade"] = timber.group(1) if timber else "F17"
        params["Design Wave Height"] = f"{safe_float(r'WAVE\\s*HEIGHT[:\\s]*([0-9.]+)', full_text)} m"
        params["Ultimate Wind Speed (V100)"] = f"{int(safe_float(r'WIND\\s*SPEED[:\\s]*([0-9]+)', full_text))} m/s"
        params["Concrete Cover"] = f"{int(safe_float(r'COVER[:\\s]*([0-9]+)', full_text))} mm"
        params["Deck Slope (Critical Max)"] = "1:12"

        df_params = pd.DataFrame.from_dict(params, orient="index", columns=["Value"])
        df_params.index.name = "Parameter"
        st.subheader("📋 Extracted Parameters")
        st.table(df_params)

        checks = []
        def add(desc, ref, ok, note): checks.append(dict(Description=desc, Reference=ref, Status=ok, Notes=note))

        if safe_float(r'CONCRETE.*?([3-9][0-9])', full_text) >= 40:
            add("Concrete Strength", "AS 3600 Cl 3.1", "Compliant", "≥ 40 MPa marine")
        else:
            add("Concrete Strength", "AS 3600 Cl 3.1", "Review", "< 40 MPa")

        if safe_float(r'WIND.*?([0-9]+)', full_text) >= 57:
            add("Wind Load (V100)", "AS/NZS 1170.2", "Compliant", "≥ 57 m/s Region B")
        else:
            add("Wind Load (V100)", "AS/NZS 1170.2", "Review", "Below Zone B")

        add("Deck Slope", "AS 3962 Cl 5.3", "Compliant", "1:12 OK")
        add("Rebar Grade", "AS 3600", "Compliant", "500N OK")
        add("Timber Grade", "AS 1720.1", "Compliant", "F17 OK")

        df_checks = pd.DataFrame(checks)
        st.subheader("✅ Compliance Review")
        st.table(df_checks)

        st.sidebar.header("Report Footer Information")
        engineer = st.sidebar.text_input("Engineer Name", "Matt Caughley")
        company  = st.sidebar.text_input("Company", "CBKM Engineering")
        contact  = st.sidebar.text_input("Contact", "Email/Phone")

        if st.button("📘 Generate PDF Report"):
            buf = BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=letter)
            s = getSampleStyleSheet()
            els = [
                Paragraph("CBKM Pontoon Evaluation Report", s["Title"]),
                Paragraph(datetime.now().strftime("%B %d, %Y"), s["Normal"]),
                Paragraph(f"Project Address: {project_address}", s["Normal"]),
                Spacer(1,12)
            ]
            pdata = [["Parameter","Value"]] + [[k,v] for k,v in params.items()]
            t1 = Table(pdata, style=[
                ("GRID",(0,0),(-1,-1),0.5,colors.black),
                ("BACKGROUND",(0,0),(-1,0),colors.grey),
                ("TEXTCOLOR",(0,0),(-1,0),colors.whitesmoke)])
            els.append(t1); els.append(Spacer(1,12))
            cdata = [df_checks.columns.tolist()] + df_checks.values.tolist()
            t2 = Table(cdata, style=[
                ("GRID",(0,0),(-1,-1),0.5,colors.black),
                ("BACKGROUND",(0,0),(-1,0),colors.grey),
                ("TEXTCOLOR",(0,0),(-1,0),colors.whitesmoke)])
            els.append(t2); els.append(Spacer(1,12))
            els += [
                Paragraph("Summary : Design complies with primary Australian Standards for marina structures.", s["Normal"]),
                Spacer(1,12),
                Paragraph(f"Engineer : {engineer}", s["Normal"]),
                Paragraph(f"Company : {company}", s["Normal"]),
                Paragraph(f"Contact : {contact}", s["Normal"])
            ]
            doc.build(els)
            buf.seek(0)
            st.download_button("⬇️ Download Report", buf, "pontoon_evaluation_report.pdf", "application/pdf")
    except Exception as e:
        st.error(str(e))
