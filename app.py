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


# ----------------- STREAMLIT SETUP -----------------

st.set_page_config(page_title="CBKM Pontoon Evaluator", layout="wide")
st.title("CBKM Pontoon Design Evaluator")

st.markdown("""
Upload pontoon design PDF drawings → extract parameters → evaluate against key Australian Standards.  
This version uses text extraction only (no OCR) so it runs reliably on Streamlit Cloud.
""")

uploaded_file = st.file_uploader("Upload pontoon PDF", type="pdf")


# ----------------- HELPERS -----------------

def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    text_all = []
    for page in reader.pages:
        t = page.extract_text() or ""
        text_all.append(t)
    raw = "\n".join(text_all)
    # normalise whitespace for regex
    return re.sub(r"\s+", " ", raw)


def safe_float(pattern: str, text: str, default: float = 0.0) -> float:
    m = re.search(pattern, text, re.I)
    try:
        return float(m.group(1)) if m else default
    except Exception:
        return default


def safe_int(pattern: str, text: str, default: int = 0) -> int:
    m = re.search(pattern, text, re.I)
    try:
        return int(m.group(1)) if m else default
    except Exception:
        return default


def detect_address(text: str) -> str:
    fallback = "145 Buss Street, Burnett Heads, QLD 4670, Australia"
    patterns = [
        r"PROJECT\s*ADDRESS[:\s]*(.*?QLD\s*\d{4})",
        r"LOCATION[:\s]*(.*?QLD\s*\d{4})",
        r"(145\s*BUSS\s*STREET.*?BURNETT\s*HEADS.*?QLD\s*\d{4})"
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return m.group(1).strip()
    return fallback


# ----------------- MAIN APP -----------------

if uploaded_file is None:
    st.info("Upload a PDF to begin.")
else:
    try:
        file_bytes = uploaded_file.read()
        full_text = extract_text_from_pdf(file_bytes)

        with st.expander("Show raw extracted text"):
            st.text_area("PDF text", full_text[:15000], height=200)

        project_address = st.text_input("Project address", detect_address(full_text))

        # -------- PARAMETER EXTRACTION (TEXT ONLY) --------
        params = {}

        # Vessel geometry
        length = safe_float(r"VESSEL\s*LENGTH\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*m", full_text)
        beam = safe_float(r"VESSEL\s*BEAM\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*m", full_text)
        if length:
            params["Vessel Length"] = f"{length} m"
        if beam:
            params["Vessel Beam"] = f"{beam} m"

        # Concrete
        conc_mp = safe_int(r"(?:PONTOON\s*)?CONCRETE\s*STRENGTH.*?([0-9]{2})\s*MPa", full_text)
        if conc_mp:
            params["Concrete Strength"] = f"{conc_mp} MPa"

        # Rebar grade
        m = re.search(r"REBAR\s*GRADE\s*=\s*([0-9A-Z]+)", full_text, re.I)
        params["Rebar Grade"] = m.group(1) if m else "N/A"

        # Cover
        cover = safe_int(r"CONCRETE\s*COVER\s*=\s*([0-9]+)\s*mm", full_text)
        if cover:
            params["Concrete Cover"] = f"{cover} mm"

        # Galvanizing
        galv = safe_int(r"GALVANIZING\s*=\s*([0-9]+)\s*g/m", full_text)
        if galv:
            params["Galvanizing"] = f"{galv} g/m²"

        # Timber grade
        m = re.search(r"\b(F[0-9]+)\b", full_text)
        params["Timber Grade"] = m.group(1) if m else "N/A"

        # Wind speed
        wind = safe_int(r"(?:ULTIMATE\s*)?WIND\s*SPEED.*?([0-9]{2})\s*m/s", full_text)
        if wind:
            params["Ultimate Wind Speed (V100)"] = f"{wind} m/s"

        # Live loads (very rough text pattern to avoid breakage)
        live_u = safe_float(r"LIVE\s*LOAD.*?([0-9]+(?:\.[0-9]+)?)\s*kPa", full_text)
        live_p = safe_float(r"POINT\s*LOAD.*?([0-9]+(?:\.[0-9]+)?)\s*kN", full_text)
        if live_u:
            params["Live Load Uniform"] = f"{live_u} kPa"
        if live_p:
            params["Live Load Point"] = f"{live_p} kN"

        # Display parameters table
        if params:
            df_params = pd.DataFrame(
                [{"Parameter": k, "Value": v} for k, v in params.items()]
            )
            st.subheader("Extracted parameters")
            st.dataframe(df_params, use_container_width=True)
        else:
            st.warning("No parameters found with current regex patterns.")

        # -------- COMPLIANCE CHECKS (SAFE, MINIMAL) --------
        checks = []

        def add_check(name: str, requirement: str, design_value: str, status: str, reference: str):
            checks.append(
                {
                    "Check": name,
                    "Requirement": requirement,
                    "Design Value": design_value,
                    "Status": status,
                    "Reference": reference,
                }
            )

        # Concrete strength
        if conc_mp:
            status = "Compliant" if conc_mp >= 40 else "Review"
            add_check(
                "Concrete strength",
                "≥ 40 MPa (marine exposure)",
                f"{conc_mp} MPa",
                status,
                "AS 3600:2018",
            )

        # Wind
        if wind:
            status = "Compliant" if wind >= 57 else "Review"
            add_check(
                "Wind (V100)",
                "≥ 57 m/s (Region B)",
                f"{wind} m/s",
                status,
                "AS/NZS 1170.2",
            )

        # Live load
        if live_u:
            status = "Compliant" if live_u >= 2.0 else "Review"
            add_check(
                "Live load (uniform)",
                "≥ 2.0 kPa",
                f"{live_u} kPa",
                status,
                "AS 3962:2020",
            )
        if live_p:
            status = "Compliant" if live_p >= 4.5 else "Review"
            add_check(
                "Live load (point)",
                "≥ 4.5 kN",
                f"{live_p} kN",
                status,
                "AS 3962:2020",
            )

        # Cover
        if cover:
            status = "Compliant" if cover >= 50 else "Review"
            add_check(
                "Concrete cover",
                "≥ 50 mm (C1/C2)",
                f"{cover} mm",
                status,
                "AS 3600:2018",
            )

        # Timber grade
        tg = params.get("Timber Grade", "N/A")
        if tg != "N/A":
            status = "Compliant" if "F17" in tg.upper() else "Review"
            add_check(
                "Timber grade",
                "F17",
                tg,
                status,
                "AS 1720.1",
            )

        if checks:
            df_checks = pd.DataFrame(checks)
            st.subheader("Compliance summary")
            st.dataframe(df_checks, use_container_width=True)
        else:
            st.info("No compliance checks run (no matching parameters).")

        # -------- PDF REPORT GENERATION --------
        st.sidebar.header("Report footer")
        engineer_name = st.sidebar.text_input("Engineer name", "Matt Caughley")
        engineer_rpeq = st.sidebar.text_input("RPEQ number", "")
        company = st.sidebar.text_input("Company", "CBKM Engineering")
        contact = st.sidebar.text_input("Contact", "Email / Phone")

        if st.button("Generate PDF report"):
            buf = BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=letter)
            styles = getSampleStyleSheet()
            elements = []

            elements.append(Paragraph("CBKM Pontoon Evaluation Report", styles["Title"]))
            elements.append(Paragraph(datetime.now().strftime("%d %B %Y"), styles["Normal"]))
            elements.append(Paragraph(f"Project address: {project_address}", styles["Normal"]))
            elements.append(Spacer(1, 12))

            # Parameters table
            if params:
                param_data = [["Parameter", "Value"]] + [
                    [k, v] for k, v in params.items()
                ]
                t1 = Table(param_data)
                t1.setStyle(
                    TableStyle(
                        [
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ]
                    )
                )
                elements.append(Paragraph("Extracted parameters", styles["Heading2"]))
                elements.append(t1)
                elements.append(Spacer(1, 12))

            # Compliance table
            if checks:
                comp_data = [list(df_checks.columns)] + df_checks.values.tolist()
                t2 = Table(comp_data)
                t2.setStyle(
                    TableStyle(
                        [
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ]
                    )
                )
                elements.append(Paragraph("Compliance summary", styles["Heading2"]))
                elements.append(t2)
                elements.append(Spacer(1, 12))

            # Short summary
            elements.append(
                Paragraph(
                    "Summary: This report is an automated screening check. "
                    "Review all results against the original design documentation and standards.",
                    styles["Normal"],
                )
            )
            elements.append(Spacer(1, 12))
            elements.append(Paragraph(f"Engineer: {engineer_name} {engineer_rpeq}", styles["Normal"]))
            elements.append(Paragraph(f"Company: {company}", styles["Normal"]))
            elements.append(Paragraph(f"Contact: {contact}", styles["Normal"]))

            doc.build(elements)
            buf.seek(0)
            st.download_button(
                "Download evaluation report (PDF)",
                buf,
                file_name="pontoon_evaluation_report.pdf",
                mime="application/pdf",
            )

    except Exception as e:
        st.error(f"Error running app: {e}")
