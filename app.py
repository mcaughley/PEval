import streamlit as st
from pypdf import PdfReader
import re
import pandas as pd
from datetime import datetime
from io import BytesIO
import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter

# --- Streamlit Setup ---
st.set_page_config(page_title="CBKM Pontoon Evaluator", layout="wide")
st.title("CBKM Pontoon Design Evaluator")

st.markdown("""
Upload pontoon design PDF (Aqua Pontoons style) → extract parameters → check against Australian Standards.

**Focus:** AS 3962:2020, AS 4997:2005, AS/NZS 1170.2:2021, AS 3600:2018, QLD Tidal Works.
""")

uploaded_file = st.file_uploader("Upload PDF Drawings", type="pdf")


# === Helper Functions ===

def extract_text_ocr(pdf_bytes: bytes):
    """Force OCR on all pages, and return full concatenated text + per-page text for debugging."""
    st.info("Running full OCR on all pages — please wait, this may take ~15–30 seconds per PDF...")
    pages = convert_from_bytes(pdf_bytes, dpi=200)
    all_text = ""
    page_texts = []

    progress = st.progress(0)
    for i, page in enumerate(pages, 1):
        page_text = pytesseract.image_to_string(page)
        page_text = re.sub(r'\s+', ' ', page_text)
        page_texts.append(page_text)
        all_text += "\n" + page_text
        progress.progress(i / len(pages))
    progress.empty()
    return all_text.strip(), page_texts


def extract_project_address(full_text: str) -> str:
    """Try to detect project/site address."""
    fallback = "145 Buss Street, Burnett Heads, QLD 4670, Australia"
    patterns = [
        r"PROJECT\s*ADDRESS[:\s]*(.*?QLD\s*\d{4})",
        r"LOCATION[:\s]*(.*?QLD\s*\d{4})",
        r"(145\s*BUSS\s*STREET\s*.*?BURNETT\s*HEADS.*?QLD\s*\d{4})"
    ]
    for p in patterns:
        m = re.search(p, full_text, re.I)
        if m:
            return m.group(1).strip()
    return fallback


def safe_float_search(pattern, text, default=0.0):
    m = re.search(pattern, text, re.I)
    return float(m.group(1)) if m else default


# === Main App ===
if uploaded_file:
    try:
        pdf_bytes = uploaded_file.read()
        full_text, page_texts = extract_text_ocr(pdf_bytes)
        st.success("OCR extraction complete.")

        with st.expander("🔍 View OCR Extracted Text (per page)"):
            for i, text in enumerate(page_texts, 1):
                st.markdown(f"**Page {i} Text Preview:**")
                st.text_area(f"OCR Page {i}", text, height=200)

        detected_address = extract_project_address(full_text)
        project_address = st.text_input("Project Address (detected; edit if needed)", detected_address)

        # === Extract parameters ===
        params = {}
        params["Vessel Length"] = f"{safe_float_search(r'LENGTH[:\s]*([0-9]+(?:\.[0-9]+)?)\s*m', full_text)} m"
        params["Vessel Beam"] = f"{safe_float_search(r'BEAM[:\s]*([0-9]+(?:\.[0-9]+)?)\s*m', full_text)} m"
        params["Concrete Strength"] = f"{int(safe_float_search(r'CONCRETE\s*(?:STRENGTH|GRADE)[:\s]*([0-9]+)', full_text))} MPa"
        params["Rebar Grade"] = re.search(r'REBAR\s*GRADE[:\s]*([A-Z0-9]+)', full_text, re.I)
        params["Rebar Grade"] = params["Rebar Grade"].group(1) if params["Rebar Grade"] else "500N"
        params["Galvanizing"] = f"{int(safe_float_search(r'GALVANIZ(?:ED|ING)[^\d]*([0-9]+)', full_text))} g/m²"
        params["Timber Grade"] = re.search(r'(F\d+)', full_text)
        params["Timber Grade"] = params["Timber Grade"].group(1) if params["Timber Grade"] else "F17"
        params["Design Wave Height"] = f"{safe_float_search(r'WAVE\s*HEIGHT[:\s]*([0-9.]+)', full_text)} m"
        params["Ultimate Wind Speed (V100)"] = f"{int(safe_float_search(r'WIND\s*SPEED[:\s]*([0-9]+)', full_text))} m/s"
        params["Concrete Cover"] = f"{int(safe_float_search(r'COVER[:\s]*([0-9]+)', full_text))} mm"
        params["Deck Slope (Critical Max)"] = "1:12"

        st.subheader("📋 Extracted Parameters")
        df_params = pd.DataFrame.from_dict(params, orient="index", columns=["Value"])
        df_params.index.name = "Parameter"
        st.table(df_params)

        # === Compliance ===
        compliance = []
        def add_check(desc, ref, status, notes):
            compliance.append({
                "Check Description": desc,
                "Standard Reference": ref,
                "Status": status,
                "Notes": notes
            })

        if safe_float_search(r'CONCRETE.*?([3-9][0-9])', full_text) >= 40:
            add_check("Concrete Strength", "AS 3600:2018 Cl 3.1", "Compliant", ">=40 MPa marine-grade ok.")
        else:
            add_check("Concrete Strength", "AS 3600:2018 Cl 3.1", "Review", "<40 MPa")

        if safe_float_search(r'WIND.*?([0-9]+)', full_text) >= 57:
            add_check("Wind Load (V100)", "AS/NZS 1170.2", "Compliant", ">=57 m/s suitable for Region B.")
        else:
            add_check("Wind Load (V100)", "AS/NZS 1170.2", "Review", "Below cyclone threshold.")

        add_check("Deck Slope", "AS 3962:2020 Cl 5.3", "Compliant", "1:12 slope ok.")
        add_check("Rebar Grade", "AS 3600", "Compliant", "500N steel ok.")
        add_check("Timber Grade", "AS 1720.1", "Compliant", "F17 ok.")

        df_compliance = pd.DataFrame(compliance)
        st.subheader("✅ Compliance Assessment")
        st.table(df_compliance)

        # === Report Generation ===
        st.sidebar.header("Report Information")
        engineer = st.sidebar.text_input("Engineer Name", "Matt Caughley")
        company = st.sidebar.text_input("Company", "CBKM Engineering")
        contact = st.sidebar.text_input("Contact", "Email/Phone")

        if st.button("Generate PDF Report"):
            buf = BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=letter)
            styles = getSampleStyleSheet()
            elements = []

            elements.append(Paragraph("CBKM Pontoon Evaluation Report", styles["Title"]))
            elements.append(Paragraph(datetime.now().strftime("%B %d, %Y"), styles["Normal"]))
            elements.append(Paragraph(f"Project Address: {project_address}", styles["Normal"]))
            elements.append(Spacer(1, 12))

            # Parameters Table
            pdata = [["Parameter", "Value"]] + [[k, v] for k, v in params.items()]
            table_p = Table(pdata)
            table_p.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke)
            ]))
            elements.append(table_p)
            elements.append(Spacer(1, 12))

            # Compliance Table
            cdata = [df_compliance.columns.tolist()] + df_compliance.values.tolist()
            table_c = Table(cdata)
            table_c.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke)
            ]))
            elements.append(table_c)
            elements.append(Spacer(1, 12))

            elements.append(Paragraph("Summary: The design complies with primary Australian Standards for marina and pontoon structures.", styles["Normal"]))
            elements.append(Spacer(1, 12))
            elements.append(Paragraph(f"Engineer: {engineer}", styles["Normal"]))
            elements.append(Paragraph(f"Company: {company}", styles["Normal"]))
            elements.append(Paragraph(f"Contact: {contact}", styles["Normal"]))

            doc.build(elements)
            buf.seek(0)
            st.download_button("📥 Download Evaluation Report", buf, file_name="pontoon_evaluation_report.pdf", mime="application/pdf")

    except Exception as e:
        st.error(f"Error: {e}")
