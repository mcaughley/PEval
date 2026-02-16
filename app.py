# app.py - Final with dynamic project address extraction from PDF + OCR for image-based pages

import streamlit as st
from pypdf import PdfReader
import re
import pandas as pd
from datetime import datetime
from io import BytesIO
import pytesseract
from PIL import Image

st.set_page_config(page_title="CBKM Pontoon Evaluator", layout="wide")

st.title("CBKM Pontoon Design Evaluator")
st.markdown("""
Upload pontoon design PDF → extract parameters → auto-check compliance against Australian Standards  
(not just project notes). Focus: AS 3962:2020, AS 4997:2005, AS/NZS 1170.2:2021, AS 3600:2018, QLD Tidal Works.
""")

uploaded_file = st.file_uploader("Upload PDF Drawings", type="pdf")

def extract_project_address(full_text: str) -> str:
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

if uploaded_file is not None:
    try:
        reader = PdfReader(uploaded_file)
        full_text = ""
        for page_num, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            if not text:  # If no text, use OCR on page images
                for img in page.images:
                    img_data = img.data
                    img_pil = Image.open(BytesIO(img_data))
                    ocr_text = pytesseract.image_to_string(img_pil)
                    text += ocr_text + "\n"
            full_text += text + "\n"

        st.success(f"PDF processed ({len(reader.pages)} pages) - OCR applied to image-based pages.")

        # Extract address dynamically
        project_address = extract_project_address(full_text)
        st.info(f"Detected Project Address: **{project_address}**")

        # Extract parameters (expanded for OCR compatibility)
        params = {}

        match = re.search(r"LIVE LOAD.*?(\d+\.\d+)\s*kPa.*?POINT LOAD.*?(\d+\.\d+)\s*kN", full_text, re.I | re.DOTALL)
        if match:
            params['live_load_uniform'] = float(match.group(1))
            params['live_load_point'] = float(match.group(2))

        match = re.search(r"ULTIMATE WIND SPEED V100\s*=\s*(\d+)m/s", full_text, re.I | re.DOTALL)
        if match:
            params['wind_ultimate'] = int(match.group(1))

        match = re.search(r"DESIGN WAVE HEIGHT\s*<\s*(\d+)mm", full_text, re.I | re.DOTALL)
        if match:
            params['wave_height'] = int(match.group(1)) / 1000.0

        match = re.search(r"DESIGN STREAM VELOCITY.*?<\s*(\d+\.\d+)\s*m/s", full_text, re.I | re.DOTALL)
        if match:
            params['current_velocity'] = float(match.group(1))

        match = re.search(r"DEBRIS LOADS\s*=\s*(\d+\.\d+)m.*?(\d+\.\d+)\s*TONNE", full_text, re.I | re.DOTALL)
        if match:
            params['debris_mat_depth'] = float(match.group(1))
            params['debris_log_mass'] = float(match.group(2))

        match = re.search(r"VESSEL LENGTH\s*=\s*(\d+\.\d+)\s*m", full_text, re.I | re.DOTALL)
        if match:
            params['vessel_length'] = float(match.group(1))
        match = re.search(r"VESSEL BEAM\s*=\s*(\d+\.\d+)\s*m", full_text, re.I | re.DOTALL)
        if match:
            params['vessel_beam'] = float(match.group(1))
        match = re.search(r"VESSEL MASS\s*=\s*(\d+,\d+)\s*kg", full_text, re.I | re.DOTALL)
        if match:
            params['vessel_mass'] = int(match.group(1).replace(',', ''))

        match = re.search(r"DEAD LOAD ONLY\s*=\s*(\d+)-(\d+)mm", full_text, re.I | re.DOTALL)
        if match:
            params['freeboard_dead_min'] = int(match.group(1))
            params['freeboard_dead_max'] = int(match.group(2))
            params['freeboard_dead'] = (params['freeboard_dead_min'] + params['freeboard_dead_max']) / 2
        match = re.search(r"MIN\s*(\d+)\s*mm", full_text, re.I | re.DOTALL)
        if match:
            params['freeboard_critical'] = int(match.group(1))

        match = re.search(r"CRITICAL DECK SLOPE\s*=\s*1:(\d+)\s*DEG", full_text, re.I | re.DOTALL)
        if match:
            params['deck_slope_max'] = int(match.group(1))

        match = re.search(r"PONTOON CONCRETE STRENGTH.*?(\d+)\s
