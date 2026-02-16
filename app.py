# Pontoon Design Evaluation Web App (Streamlit Version)
# Version: 1.0
# Author: Grok AI (built by xAI)
# Date: February 16, 2026
# Description: This is a web-based version of the pontoon design evaluator using Streamlit.
# It allows uploading a PDF file, extracts text using PyPDF2 (for text-based PDFs) or pytesseract for OCR on image-based PDFs/pages.
# Note: For OCR, install pytesseract and tesseract-ocr on your system (e.g., pip install pytesseract, and download tesseract executable).
# Run with: streamlit run this_file.py

import streamlit as st
import json
import datetime
import pandas as pd
import re
from typing import Dict, Any
from pypdf2 import PdfReader
import io
from PIL import Image
import pytesseract  # For OCR on image-based PDFs

# Audit Log File
AUDIT_LOG_FILE = "pontoon_evaluation_audit.log"

def log_action(message: str):
    timestamp = datetime.datetime.now().isoformat()
    with open(AUDIT_LOG_FILE, 'a') as log_file:
        log_file.write(f"[{timestamp}] {message}\n")

@st.cache_data
def extract_params_from_pdf(uploaded_file) -> Dict[str, Any]:
    """Extracts design parameters from the uploaded PDF using text parsing or OCR."""
    full_text = ""
    try:
        pdf_reader = PdfReader(uploaded_file)
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
            else:
                # If no text, use OCR
                images = page.images
                for img in images:
                    img_data = img.data
                    img_pil = Image.open(io.BytesIO(img_data))
                    ocr_text = pytesseract.image_to_string(img_pil)
                    full_text += ocr_text + "\n"
        log_action("Extracted text from PDF")
    except Exception as e:
        log_action(f"Error extracting from PDF: {str(e)}")
        st.error(f"Error processing PDF: {str(e)}")
        return {}

    # Parse key values (same as before)
    params = {}
    match = re.search(r"LIVE LOAD (\d+\.\d+) kPa OR POINT LOAD (\d+\.\d+) kN", full_text, re.IGNORECASE)
    if match:
        params['live_load_uniform'] = float(match.group(1))
        params['live_load_point'] = float(match.group(2))
    
    match = re.search(r"ULTIMATE WIND SPEED V100 = (\d+)m/s", full_text, re.IGNORECASE)
    if match:
        params['wind_ultimate'] = int(match.group(1))
    
    match = re.search(r"DESIGN WAVE HEIGHT<(\d+)mm", full_text, re.IGNORECASE)
    if match:
        params['wave_height'] = int(match.group(1)) / 1000
    
    match = re.search(r"DESIGN STREAM VELOCITY .* <(\d+\.\d+) m/s", full_text, re.IGNORECASE)
    if match:
        params['current_velocity'] = float(match.group(1))
    
    match = re.search(r"DEBRIS LOADS = (\d+\.\d+)m DEEP DEBRIS MAT, OR (\d+\.\d+) TONNE LOG", full_text, re.IGNORECASE)
    if match:
        params['debris_mat_depth'] = float(match.group(1))
        params['debris_log_mass'] = float(match.group(2))
    
    match = re.search(r"DESIGN WET BERTH VESSEL LENGTH = (\d+\.\d+) m", full_text, re.IGNORECASE)
    if match:
        params['vessel_length'] = float(match.group(1))
    
    match = re.search(r"DESIGN WET BERTH VESSEL BEAM = (\d+\.\d+) m", full_text, re.IGNORECASE)
    if match:
        params['vessel_beam'] = float(match.group(1))
    
    match = re.search(r"DESIGN WET BERTH VESSEL MASS = (\d+,\d+) kg", full_text, re.IGNORECASE)
    if match:
        params['vessel_mass'] = int(match.group(1).replace(',', ''))
    
    match = re.search(r"DEAD LOAD ONLY = (\d+)-(\d+)mm", full_text, re.IGNORECASE)
    if match:
        params['freeboard_dead'] = (int(match.group(1)) + int(match.group(2))) / 2
    
    match = re.search(r"CRITICAL FLOTATION/STABILITY CASE = MIN (\d+) mm", full_text, re.IGNORECASE)
    if match:
        params['freeboard_critical'] = int(match.group(1))
    
    match = re.search(r"CRITICAL DECK SLOPE = 1:(\d+) DEG", full_text, re.IGNORECASE)
    if match:
        params['deck_slope_max'] = int(match.group(1))
    
    match = re.search(r"PONTOON CONCRETE STRENGTH TO BE (\d+) MPa", full_text, re.IGNORECASE)
    if match:
        params['concrete_strength'] = int(match.group(1))
    
    match = re.search(r"MINIMUM COVER TO THE REINFORCEMENT - (\d+) mm", full_text, re.IGNORECASE)
    if match:
        params['concrete_cover'] = int(match.group(1))
    
    match = re.search(r"COATING MASS NOT LESS THAN (\d+) g/sqm", full_text, re.IGNORECASE)
    if match:
        params['steel_galvanizing'] = int(match.group(1))
    
    match = re.search(r"MINIMUM GRADE (\d+ T\d)", full_text, re.IGNORECASE)
    if match:
        params['aluminium_grade'] = match.group(1)
    
    match = re.search(r"MINIMUM (F\d+)", full_text, re.IGNORECASE)
    if match:
        params['timber_grade'] = match.group(1)
    
    match = re.search(r"FIXINGS TO BE (\d+) GRADE STAINLESS STEEL", full_text, re.IGNORECASE)
    if match:
        params['fixings_grade'] = match.group(1) + " SS"
    
    match = re.search(r"MAX (\d+)mm SCOUR", full_text, re.IGNORECASE)
    if match:
        params['scour_allowance'] = int(match.group(1))
    
    match = re.search(r"MAX OUT-OF-PLANE TOLERANCE .* = (\d+)mm", full_text, re.IGNORECASE)
    if match:
        params['pile_tolerance'] = int(match.group(1))
    
    match = re.search(r"UNDRAINED COHESION = (\d+)kPa", full_text, re.IGNORECASE)
    if match:
        params['soil_cohesion'] = int(match.group(1))
    
    # Defaults for missing
    params.setdefault('berth_length', params.get('vessel_length', 0) * 1.1)
    params.setdefault('berth_width', params.get('vessel_beam', 0) * 1.5)
    params.setdefault('gangway_width', 2.0)
    params.setdefault('gangway_slope', 0.25)
    params.setdefault('berthing_speed', 0.3)
    params.setdefault('berthing_energy', 0.5 * params.get('vessel_mass', 0) * (params['berthing_speed'] ** 2) / 1000)
    params.setdefault('pile_diameter', 450)
    
    log_action(f"Extracted params: {json.dumps(params)}")
    return params

class PontoonEvaluator:
    # (The class remains the same as in the previous version - init, add_assumption, add_recommendation, all check methods, evaluate_design, generate_report)

# Streamlit App
st.title("Pontoon Design Evaluation Web App")
st.write("Upload your pontoon design PDF to evaluate compliance with Australian Standards.")

uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file is not None:
    design_params = extract_params_from_pdf(uploaded_file)
    if design_params:
        evaluator = PontoonEvaluator(design_params)
        report = evaluator.evaluate_design()
        st.markdown(report)
        st.download_button("Download Report", report, file_name="pontoon_report.md")
    else:
        st.error("Could not extract parameters from PDF. Ensure it's text-searchable or try OCR mode.")

# Add more UI elements if needed, like manual param input for overrides
if st.checkbox("Manual Parameter Override"):
    # Add form for params
    pass  # Implement if desired