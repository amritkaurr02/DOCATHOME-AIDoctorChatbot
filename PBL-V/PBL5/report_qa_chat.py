import json
import os
import uuid
import re
from datetime import datetime

import streamlit as st
import google.generativeai as genai


class ReportQASystem:
    """
    Medical report Q&A system using Gemini (google-generativeai SDK)
    """

    def __init__(self, gemini_api_key=None):
        self.analysis_store = self._load_analysis_store()

        # ✅ Streamlit secrets (Option 1)
        api_key = gemini_api_key or st.secrets.get("GOOGLE_API_KEY")
        self.model = None

        if api_key:
            genai.configure(api_key=api_key)
            # ✅ Free-tier safe model
            self.model = genai.GenerativeModel("gemini-2.5-flash")
        else:
            print("⚠️ Gemini API key not found. Running in offline mode.")

    # -----------------------------
    # Storage
    # -----------------------------
    def _load_analysis_store(self):
        if os.path.exists("analysis_store.json"):
            try:
                with open("analysis_store.json", "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
        return {"analyses": []}

    def _save_store(self):
        with open("analysis_store.json", "w", encoding="utf-8") as f:
            json.dump(self.analysis_store, f, indent=2, ensure_ascii=False)

    # -----------------------------
    # Upload report
    # -----------------------------
    def upload_report(self, filename, content):
        report_id = str(uuid.uuid4())
        self.analysis_store["analyses"].append({
            "id": report_id,
            "filename": filename,
            "analysis": content,
            "uploaded_at": datetime.now().isoformat(),
            "ai_summary": None
        })
        self._save_store()
        return report_id

    # -----------------------------
    # Offline parsing
    # -----------------------------
    def _parse_report_values(self, text):
        pattern = r"([A-Z][A-Z0-9\s]{1,30})[:\s]+([\d.]+)\s*(HIGH|LOW|NORMAL)?"
        data = {}

        for line in text.splitlines():
            match = re.search(pattern, line.upper())
            if match:
                param, value, status = match.groups()
                data[param.strip()] = {
                    "value": value,
                    "status": status.capitalize() if status else "Normal"
                }
        return data

    def _offline_summary(self, parsed):
        if not parsed:
            return "⚠️ Unable to interpret report content."

        high, low, normal = [], [], []

        for key, val in parsed.items():
            if val["status"] == "High":
                high.append(f"{key}: {val['value']} ↑")
            elif val["status"] == "Low":
                low.append(f"{key}: {val['value']} ↓")
            else:
                normal.append(f"{key}: {val['value']}")

        output = []

        if normal:
            output.append("✔ Normal Values:")
            output.extend(f"- {x}" for x in normal)

        if high:
            output.append("\n⚠ High Values:")
            output.extend(f"- {x}" for x in high)

        if low:
            output.append("\n⚠ Low Values:")
            output.extend(f"- {x}" for x in low)

        output.append("\n🚨 Recommendation:")
        output.append("- Please consult a qualified medical professional.")

        return "\n".join(output)

    # -----------------------------
    # Analyze report
    # -----------------------------
    def analyze_report(self, filename, content):
        report_id = self.upload_report(filename, content)
        summary = None

        if self.model:
            try:
                response = self.model.generate_content(
                    f"""
You are a medical assistant.

Tasks:
1. Patient-friendly summary
2. Highlight abnormal values
3. Simple explanation (non-diagnostic)
4. Whether doctor consultation is advised

Rules:
- Do NOT diagnose
- Do NOT assume missing values

Medical Report:
{content}
"""
                )
                summary = response.text

            except Exception as e:
                if "429" in str(e):
                    print("⚠️ Gemini quota exceeded. Falling back to offline mode.")
                else:
                    print(f"[Gemini failed] {e}")

        if not summary:
            summary = self._offline_summary(
                self._parse_report_values(content)
            )

        for report in self.analysis_store["analyses"]:
            if report["id"] == report_id:
                report["ai_summary"] = summary

        self._save_store()
        return summary

    # -----------------------------
    # Answer questions
    # -----------------------------
    def answer_question(self, question):
        reports = self.analysis_store.get("analyses", [])

        if not reports:
            return "⚠️ No reports uploaded."

        combined_reports = "\n\n".join(
            report["analysis"] for report in reports
        )

        if self.model:
            try:
                response = self.model.generate_content(
                    f"""
Answer ONLY using the provided report data.

Rules:
- Do not guess
- Do not add new medical facts
- If data is missing, clearly say so

Reports:
{combined_reports}

Question:
{question}
"""
                )
                return response.text

            except Exception as e:
                if "429" in str(e):
                    return "⚠️ AI quota exceeded. Please try again later."
                print(f"[Gemini failed] {e}")

        return self._offline_summary(
            self._parse_report_values(combined_reports)
        )
