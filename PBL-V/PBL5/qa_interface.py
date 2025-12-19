import json
import os
from datetime import datetime
import google.generativeai as genai


class ReportQASystem:
    """
    Handles report storage, retrieval, and Gemini-based Q&A.
    """
    def __init__(self, gemini_api_key=None):
        self.gemini_api_key = gemini_api_key
        self.analysis_store = self._load_store()

    # -------------------------
    # Storage Management
    # -------------------------
    def _load_store(self):
        """Load existing analysis data from file or create new."""
        if os.path.exists("analysis_store.json"):
            try:
                with open("analysis_store.json", "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {"analyses": []}
        return {"analyses": []}

    def _save_store(self):
        """Save current analyses to file."""
        with open("analysis_store.json", "w", encoding="utf-8") as f:
            json.dump(self.analysis_store, f, indent=2)

    # -------------------------
    # Add / Manage Reports
    # -------------------------
    def add_report_analysis(self, filename, analysis_text):
        """Add a new report analysis entry."""
        entry = {
            "filename": filename,
            "analysis": analysis_text,
            "date": datetime.now().isoformat(),
            "findings": [],
        }
        self.analysis_store["analyses"].append(entry)
        self._save_store()

    # -------------------------
    # Q&A Processing
    # -------------------------
    def answer_question(self, question):
        """Use Gemini to answer a question based on all stored reports."""
        if not self.analysis_store["analyses"]:
            return "⚠️ No reports uploaded yet. Please upload a report first."

        combined_text = "\n\n".join(
            [f"Report: {a['filename']}\n{a['analysis']}" for a in self.analysis_store["analyses"]]
        )

        prompt = (
            "You are a highly skilled radiology AI assistant.\n"
            "Based on the following medical reports, answer the user's question clearly.\n\n"
            f"---\nReports:\n{combined_text}\n---\n\n"
            f"Question: {question}\n\nAnswer concisely and factually."
        )

        # Handle both test (no API key) and live Gemini use
        if not self.gemini_api_key:
            return f"(Simulated answer) You asked: '{question}'. I would analyze the reports to provide insights."

        try:
            genai.configure(api_key=self.gemini_api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"⚠️ Gemini Error: {e}"


# -------------------------------------
# Chat System Wrapper for Report Q&A
# -------------------------------------
class ReportQAChat:
    """
    Maintains a simple in-memory chat thread for report Q&A.
    """
    def __init__(self):
        self.chat_history = []

    def add_message(self, role, content):
        """Store chat message."""
        self.chat_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

    def get_history(self):
        """Return the full chat conversation."""
        return self.chat_history
