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
    fallback = ""
    text = re.sub(r"(PROJECT\s*(?:ADDRESS|USE ADDRESS|NEW COMMERCIAL USE PONTOON|PONTOON)?\s*:\s*)", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    if re.search(r"145\s*BUSS\s*STREET.*BURNETT\s*HEADS.*4670", text, re.I | re.DOTALL):
        return "145 Buss Street, Burnett Heads, QLD 4670, Australia"
    return fallback

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

        params = {}

        if m := re.search(r"LIVE LOAD.*?(\d+\.?\d*)\s*kPa", full_text, re.I | re.DOTALL):
            params['live_load_uniform'] = float(m.group(1))
        if m := re.search(r"POINT LOAD.*?(\d+\.?\d*)\s*kN", full_text, re.I | re.DOTALL):
            params['live_load_point'] = float(m.group(1))
        if m := re.search(r"V100\s*=\s*(\d+)\s*m/s", full_text, re.I | re.DOTALL):
            params['wind_ultimate'] = int(m.group(1))
        if m := re.search(r"WAVE HEIGHT.*?(\d+)\s*mm", full_text, re.I | re.DOTALL):
            params['wave_height'] = int(m.group(1)) / 1000.0
        if m := re.search(r"VELOCITY.*?(\d+\.?\d*)\s*m/s", full_text, re.I | re.DOTALL):
            params['current_velocity'] = float(m.group(1))
        if m := re.search(r"DEBRIS.*?(\d+\.?\d*)\s*m", full_text, re.I | re.DOTALL):
            params['debris_mat_depth'] = float(m.group(1))
        if m := re.search(r"LENGTH\s*=\s*(\d+\.?\d*)\s*m", full_text, re.I | re.DOTALL):
            params['vessel_length'] = float(m.group(1))
        if m := re.search(r"BEAM\s*=\s*(\d+\.?\d*)\s*m", full_text, re.I | re.DOTALL):
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

        st.subheader("Extracted Parameters")
        if params:
            df_params = pd.DataFrame(list(params.items()), columns=["Parameter", "Value"])
            df_params["Value"] = df_params["Value"].astype(str)
            st.dataframe(df_params, width='stretch')

        compliance_checks = [
            {"name": "Live load uniform", "req": "≥ 3.0 kPa", "key": "live_load_uniform", "func": lambda v: v >= 3.0 if v is not None else False, "ref": "AS 3962:2020 §2 & 4"},
            {"name": "Live load point", "req": "≥ 4.5 kN", "key": "live
