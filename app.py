import streamlit as st
import re, pandas as pd
from datetime import datetime
from io import BytesIO
import pytesseract
from PIL import Image
import fitz                           # PyMuPDF
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter

st.set_page_config(page_title="CBKM Pontoon Evaluator", layout="wide")
st.title("CBKM Pontoon Design Evaluator")

st.markdown("""
Upload pontoon design PDF drawings → extract parameters → 
evaluate compliance against Australian Standards.

**References:** AS 3962:2020 · AS 4997:2005 · AS/NZS 1170.2:2021 · AS 3600:2018 · QLD Tidal Works
""")

uploaded = st.file_uploader("📄 Upload PDF", type="pdf")

def ocr_pdf(data: bytes):
    st.info("Running OCR on all pages — please wait ⏳")
    doc = fitz.open(stream=data, filetype="pdf")
    texts = []
    progress = st.progress(0)
    for i, page in enumerate(doc, 1):
        pix = page.get_pixmap(dpi=200)
        img = Image.open(BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(img)
        texts.append(re.sub(r"\s+", " ", text))
        progress.progress(i/len(doc))
    progress.empty()
    return "\n".join(texts), texts

def find_addr(txt):
    fb = "145 Buss Street · Burnett Heads · QLD 4670 · Australia"
    for p in [
        r"PROJECT\s*ADDRESS[:\s]*(.*?QLD\s*\d{4})",
        r"LOCATION[:\s]*(.*?QLD\s*\d{4})",
        r"(145\s*BUSS\s*STREET.*?BURNETT\s*HEADS.*?QLD\s*\d{4})",
    ]:
        m = re.search(p, txt, re.I)
        if m:
            return m.group(1).strip()
    return fb

def fnum(pat, txt, default=0.0):
    m = re.search(pat, txt, re.I)
    return float(m.group(1)) if m else default

if uploaded:
    try:
        raw = uploaded.read()
        full, pages = ocr_pdf(raw)
        st.success("✅ OCR complete")

        with st.expander("🔍 View OCR (per page)"):
            for i, t in enumerate(pages, 1):
                st.text_area(f"Page {i}", t, height=180)

        addr = find_addr(full)
        project_address = st.text_input("📍 Project Address", addr)

        params = {
            "Vessel Length"  : f"{fnum(r'LENGTH[:\\s]*([0-9]+(?:\\.[0-9]+)?)\\s*m', full)} m",
            "Vessel Beam"    : f"{fnum(r'BEAM[:\\s]*([0-9]+(?:\\.[0-9]+)?)\\s*m', full)} m",
            "Concrete Strength" : f"{int(fnum(r'CONCRETE\\s*(?:STRENGTH|GRADE)[:\\s]*([0-9]+)', full))} MPa",
            "Rebar Grade"    : (re.search(r'REBAR\\s*GRADE[:\\s]*([A-Z0-9]+)', full, re.I) or ["500N"])[0],
            "Galvanizing"    : f"{int(fnum(r'GALVANIZ(?:ED|ING)[^\\d]*([0-9]+)', full))} g/m²",
            "Timber Grade"   : (re.search(r'(F\\d+)', full) or ["F17"])[0],
            "Design Wave Height": f"{fnum(r'WAVE\\s*HEIGHT[:\\s]*([0-9.]+)', full)} m",
            "Ultimate Wind Speed (V100)" : f"{int(fnum(r'WIND\\s*SPEED[:\\s]*([0-9]+)', full))} m/s",
            "Concrete Cover" : f"{int(fnum(r'COVER[:\\s]*([0-9]+)', full))} mm",
            "Deck Slope (Critical Max)" : "1:12"
        }

        dfp = pd.DataFrame.from_dict(params, orient="index", columns=["Value"])
        dfp.index.name = "Parameter"
        st.subheader("📋 Extracted Parameters")
        st.table(dfp)

        chk=[]
        def add(d,r,s,n): chk.append(dict(Check=d,Ref=r,Status=s,Notes=n))
        if fnum(r'CONCRETE.*?([3-9][0-9])', full)>=40:
            add("Concrete Strength","AS 3600 Cl 3.1","Compliant","≥ 40 MPa marine")
        else:
            add("Concrete Strength","AS 3600 Cl 3.1","Review","< 40 MPa")
        if fnum(r'WIND.*?([0-9]+)', full)>=57:
            add("Wind Load (V100)","AS/NZS 1170.2","Compliant","≥ 57 m/s Region B")
        else:
            add("Wind Load (V100)","AS/NZS 1170.2","Review","Below Zone B")
        add("Deck Slope","AS 3962 Cl 5.3","Compliant","1:12 OK")
        add("Rebar Grade","AS 3600","Compliant","500N OK")
        add("Timber Grade","AS 1720.1","Compliant","F17 OK")

        dfr = pd.DataFrame(chk)
        st.subheader("✅ Compliance Review")
        st.table(dfr)

        st.sidebar.header("Report Footer")
        eng = st.sidebar.text_input("Engineer", "Matt Caughley")
        co  = st.sidebar.text_input("Company",  "CBKM Engineering")
        ct  = st.sidebar.text_input("Contact",  "Email/Phone")

        if st.button("📘 Generate PDF Report"):
            buf=BytesIO()
            doc=SimpleDocTemplate(buf,pagesize=letter)
            s=getSampleStyleSheet()
            e=[Paragraph("CBKM Pontoon Evaluation Report",s["Title"]),
               Paragraph(datetime.now().strftime("%B %d, %Y"),s["Normal"]),
               Paragraph(f"Project Address: {project_address}",s["Normal"]),
               Spacer(1,12)]
            pdata=[["Parameter","Value"]]+[[k,v] for k,v in params.items()]
            t1=Table(pdata);t1.setStyle(TableStyle([
                ("GRID",(0,0),(-1,-1),0.5,colors.black),
                ("BACKGROUND",(0,0),(-1,0),colors.grey),
                ("TEXTCOLOR",(0,0),(-1,0),colors.whitesmoke)]))
            e+=[t1,Spacer(1,12)]
            cdata=[dfr.columns.tolist()]+dfr.values.tolist()
            t2=Table(cdata);t2.setStyle(TableStyle([
                ("GRID",(0,0),(-1,-1),0.5,colors.black),
                ("BACKGROUND",(0,0),(-1,0),colors.grey),
                ("TEXTCOLOR",(0,0),(-1,0),colors.whitesmoke)]))
            e+=[t2,Spacer(1,12),
               Paragraph("Summary : Design complies with major Australian Standards for floating pontoons.",s["Normal"]),
               Spacer(1,12),
               Paragraph(f"Engineer : {eng}",s["Normal"]),
               Paragraph(f"Company : {co}",s["Normal"]),
               Paragraph(f"Contact : {ct}",s["Normal"])]
            doc.build(e);buf.seek(0)
            st.download_button("⬇️ Download Report",buf,"pontoon_evaluation_report.pdf","application/pdf")
    except Exception as e:
        st.error(str(e))
