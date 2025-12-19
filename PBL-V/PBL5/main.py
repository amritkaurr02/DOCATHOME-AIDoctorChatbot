import io
import os
import re
import json
import uuid
import base64
import pydicom
import nibabel as nib
import numpy as np
import cv2
from PIL import Image
from datetime import datetime
from Bio import Entrez
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import google.generativeai as genai  # ✅ Gemini SDK

# Configure email for PubMed
Entrez.email = "amrit23@gmail.com"

# ---------------------------
# File Processing
# ---------------------------
def process_file(uploaded_file):
    """Process medical image files (JPG, PNG, DICOM, NIfTI)"""
    ext = uploaded_file.name.split('.')[-1].lower()

    if ext in ['jpg', 'jpeg', 'png']:
        image = Image.open(uploaded_file).convert('RGB')
        return {"type": "image", "data": image, "array": np.array(image)}

    elif ext == 'dcm':
        dicom = pydicom.dcmread(uploaded_file)
        img_array = dicom.pixel_array
        img_array = ((img_array - img_array.min()) / (img_array.max() - img_array.min()) * 255).astype(np.uint8)
        return {"type": "dicom", "data": Image.fromarray(img_array), "array": img_array}

    elif ext in ['nii', 'nii.gz']:
        temp_path = f"temp_{uuid.uuid4()}.nii.gz"
        with open(temp_path, 'wb') as f:
            f.write(uploaded_file.getvalue())

        nii_img = nib.load(temp_path)
        img_array = nii_img.get_fdata()[:, :, nii_img.shape[2] // 2]
        img_array = ((img_array - img_array.min()) / (img_array.max() - img_array.min()) * 255).astype(np.uint8)
        os.remove(temp_path)
        return {"type": "nifti", "data": Image.fromarray(img_array), "array": img_array}

    return None

# ---------------------------
# Heatmap Generation
# ---------------------------
def generate_heatmap(image_array):
    """Generate heatmap overlay for visualization"""
    if len(image_array.shape) == 3:
        gray_image = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
    else:
        gray_image = image_array

    heatmap = cv2.applyColorMap(gray_image, cv2.COLORMAP_JET)

    if len(image_array.shape) == 2:
        image_array = cv2.cvtColor(image_array, cv2.COLOR_GRAY2RGB)

    overlay = cv2.addWeighted(heatmap, 0.5, image_array, 0.5, 0)
    return Image.fromarray(overlay), Image.fromarray(heatmap)

# ---------------------------
# Extract Findings & Keywords
# ---------------------------
def extract_findings_and_keywords(analysis_text):
    """Extract findings and keywords from analysis text"""
    findings = []
    keywords = []

    if "Impression:" in analysis_text:
        impression_section = analysis_text.split("Impression:")[1].strip()
        numbered_items = impression_section.split("\n")

        for item in numbered_items:
            item = item.strip()
            if item and (item[0].isdigit() or item[0] in ['-', '*']):
                clean_item = item
                if item[0].isdigit() and "." in item[:3]:
                    clean_item = item.split(".", 1)[1].strip()
                elif item[0] in ['-', '*']:
                    clean_item = item[1:].strip()
                findings.append(clean_item)

                for word in clean_item.split():
                    word = word.lower().strip(',.:;()')
                    if len(word) > 4 and word not in ['about', 'with', 'that', 'this', 'these']:
                        keywords.append(word)

    common_terms = [
        "pneumonia", "infiltrates", "opacities", "nodule", "mass", "tumor", "cardiomegaly",
        "effusion", "consolidation", "atelectasis", "edema", "fracture", "fibrosis", "emphysema",
        "pneumothorax", "metastasis"
    ]
    for term in common_terms:
        if term in analysis_text.lower() and term not in keywords:
            keywords.append(term)

    keywords = list(dict.fromkeys(keywords))
    return findings, keywords[:5]

# ---------------------------
# AI Image Analysis (Gemini)
# ---------------------------
def analyze_image(image, api_key, enable_xai=True):
    """Analyze medical image using Gemini (Google Generative AI)"""
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    encoded_image = base64.b64encode(buffered.getvalue()).decode()

    genai.configure(api_key=api_key)

    prompt = """
    Provide a detailed medical analysis of this image.
    Include:
    1. Description of key findings
    2. Possible diagnoses
    3. Recommendations for clinical correlation or follow-up
    Format with "Radiological Analysis" and "Impression" sections.
    """

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")  # or gemini-1.5-pro
        response = model.generate_content([
            prompt,
            {"mime_type": "image/png", "data": base64.b64decode(encoded_image)}
        ])

        analysis = response.text
        findings, keywords = extract_findings_and_keywords(analysis)
        return {
            "id": str(uuid.uuid4()),
            "analysis": analysis,
            "findings": findings,
            "keywords": keywords,
            "date": datetime.now().isoformat()
        }

    except Exception as e:
        return {
            "id": str(uuid.uuid4()),
            "analysis": f"Error analyzing image: {str(e)}",
            "findings": [],
            "keywords": [],
            "date": datetime.now().isoformat()
        }

# ---------------------------
# PubMed Search
# ---------------------------
def search_pubmed(keywords, max_results=5):
    """Search PubMed for relevant articles"""
    if not keywords:
        return []

    query = ' AND '.join(keywords)
    try:
        handle = Entrez.esearch(db="pubmed", term=query, retmax=max_results)
        results = Entrez.read(handle)

        if not results["IdList"]:
            return []

        fetch_handle = Entrez.efetch(db="pubmed", id=results["IdList"], rettype="medline", retmode="text")
        records = fetch_handle.read().split('\n\n')

        publications = []
        for record in records:
            if not record.strip():
                continue

            pub_data = {"id": "", "title": "", "journal": "", "year": ""}
            for line in record.split('\n'):
                if line.startswith('PMID-'):
                    pub_data["id"] = line[6:].strip()
                elif line.startswith('TI  -'):
                    pub_data["title"] = line[6:].strip()
                elif line.startswith('TA  -'):
                    pub_data["journal"] = line[6:].strip()
                elif line.startswith('DP  -'):
                    year_match = re.findall(r"\b\d{4}\b", line)
                    pub_data["year"] = year_match[0] if year_match else "2024"

            if pub_data["id"]:
                publications.append(pub_data)

        return publications

    except Exception as e:
        print(f"Error searching PubMed: {e}")
        return []

# ---------------------------
# PDF Report Generation
# ---------------------------
def generate_report(data, include_references=True, filename="medical_report.pdf"):
    """Generate PDF report"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, spaceAfter=12)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Heading2'], fontSize=14, spaceAfter=8)

    content = []
    content.append(Paragraph("Medical Imaging Analysis Report", title_style))
    content.append(Spacer(1, 12))
    content.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
    content.append(Paragraph(f"Report ID: {data['id']}", styles["Normal"]))
    if 'filename' in data:
        content.append(Paragraph(f"Image: {data['filename']}", styles["Normal"]))
    content.append(Spacer(1, 12))

    content.append(Paragraph("Analysis Result", subtitle_style))
    content.append(Paragraph(data['analysis'], styles["Normal"]))
    content.append(Spacer(1, 12))

    if data.get('findings'):
        content.append(Paragraph("Key Findings", subtitle_style))
        for idx, finding in enumerate(data['findings'], 1):
            content.append(Paragraph(f"{idx}. {finding}", styles["Normal"]))
        content.append(Spacer(1, 12))

    if data.get('keywords'):
        content.append(Paragraph("Keywords", subtitle_style))
        content.append(Paragraph(", ".join(data['keywords']), styles["Normal"]))
        content.append(Spacer(1, 12))

    if include_references:
        pubmed_results = search_pubmed(data.get('keywords', []), max_results=3)
        if pubmed_results:
            content.append(Paragraph("Relevant Medical Literature", subtitle_style))
            for ref in pubmed_results:
                content.append(Paragraph(f"{ref['title']}", styles["Normal"]))
                content.append(Paragraph(f"{ref['journal']}, {ref['year']} (PMID: {ref['id']})", styles["Normal"]))
            content.append(Spacer(1, 12))

    doc.build(content)
    buffer.seek(0)

    with open(filename, "wb") as f:
        f.write(buffer.read())

    print(f"✅ PDF Report saved as {filename}")
    return filename

# ---------------------------
# Storage Handling
# ---------------------------
def get_analysis_store():
    """Retrieve saved analyses"""
    if os.path.exists("analysis_store.json"):
        with open("analysis_store.json", "r") as f:
            return json.load(f)
    return {"analyses": []}

def save_analysis(analysis_data, filename="unknown.jpg"):
    """Save analysis to JSON"""
    store = get_analysis_store()
    analysis_data["filename"] = filename
    store["analyses"].append(analysis_data)

    with open("analysis_store.json", "w") as f:
        json.dump(store, f)

    return analysis_data

def get_analysis_by_id(analysis_id):
    """Get a specific analysis by ID"""
    store = get_analysis_store()
    for analysis in store["analyses"]:
        if analysis["id"] == analysis_id:
            return analysis
    return None

def get_latest_analyses(limit=5):
    """Get the most recent analyses"""
    store = get_analysis_store()
    sorted_analyses = sorted(store["analyses"],
                             key=lambda x: x.get("date", ""),
                             reverse=True)
    return sorted_analyses[:limit]

def extract_common_findings():
    """Extract and summarize common findings from all stored analyses"""
    store = get_analysis_store()
    keyword_counts = {}
    for analysis in store["analyses"]:
        for keyword in analysis.get("keywords", []):
            if keyword in keyword_counts:
                keyword_counts[keyword] += 1
            else:
                keyword_counts[keyword] = 1
    sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
    return sorted_keywords

def generate_statistics_report():
    """Generate a statistical report of findings"""
    store = get_analysis_store()
    if not store["analyses"]:
        return None

    # count analyses by type
    type_counts = {}
    for analysis in store["analyses"]:
        analysis_type = analysis.get("type", "unknown")
        if analysis_type in type_counts:
            type_counts[analysis_type] += 1
        else:
            type_counts[analysis_type] = 1

    # Get common findings
    common_findings = extract_common_findings()

    # create report
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    content = []
    content.append(Paragraph("Medical Imaging Statistics Report", styles["Title"]))
    content.append(Spacer(1, 12))

    # overall Statistics
    content.append(Paragraph("Overall Statistics", styles["Heading2"]))
    content.append(Paragraph(f"Total analyses: {len(store['analyses'])}", styles["Normal"]))
    content.append(Spacer(1, 12))

    # Analysis types
    if type_counts:
        content.append(Paragraph("Analysis Types", styles["Heading2"]))
        for type_name, count in type_counts.items():
            content.append(Paragraph(f"{type_name.capitalize()}: {count}", styles["Normal"]))
        content.append(Spacer(1, 12))

    # common findings
    if common_findings:
        content.append(Paragraph("Common Findings", styles["Heading2"]))
        for keyword, count in common_findings[:10]:
            content.append(Paragraph(f"{keyword.capitalize()}: {count} occurrences", styles["Normal"]))

    doc.build(content)
    buffer.seek(0)
    return buffer
