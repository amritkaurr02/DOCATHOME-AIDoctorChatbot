# chat_system_medical_api.py
import json
import os
import uuid
import time
from datetime import datetime
import requests

# ============================================================
# STORAGE
# ============================================================
STORE_PATH = "chat_store.json"
CACHE_FILE = "api_cache.json"

def get_chat_store():
    if os.path.exists(STORE_PATH):
        try:
            with open(STORE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"rooms": {}}

def save_chat_store(store):
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)

# ============================================================
# CHAT ROOMS
# ============================================================
def create_chat_room(case_id=None, creator_name="Unknown", case_description="General Case"):
    store = get_chat_store()
    case_id = case_id or str(uuid.uuid4())
    if case_id not in store["rooms"]:
        store["rooms"][case_id] = {
            "id": case_id,
            "creator": creator_name,
            "description": case_description,
            "created_at": datetime.now().isoformat(),
            "participants": [creator_name, "Dr. AI Assistant"],
            "messages": [
                {
                    "id": str(uuid.uuid4()),
                    "user": "Dr. AI Assistant",
                    "content": f"👋 Welcome to '{case_description}'. I am Dr. AI — your medical assistant.",
                    "timestamp": datetime.now().isoformat()
                }
            ]
        }
        save_chat_store(store)
    return case_id

def add_message(case_id, user, content):
    store = get_chat_store()
    if case_id in store["rooms"]:
        store["rooms"][case_id]["messages"].append({
            "id": str(uuid.uuid4()),
            "user": user,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        save_chat_store(store)

def get_messages(case_id):
    store = get_chat_store()
    return store["rooms"].get(case_id, {}).get("messages", [])

def get_available_rooms():
    store = get_chat_store()
    return list(store["rooms"].values())

# ============================================================
# RAPIDAPI SETTINGS
# ============================================================
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
if not RAPIDAPI_KEY:
    raise Exception("RAPIDAPI_KEY environment variable is not set!")

RAPIDAPI_HOST = "ai-doctor-api-ai-medical-chatbot-healthcare-ai-assistant.p.rapidapi.com"
BASE_URL = f"https://{RAPIDAPI_HOST}/chat?noqueue=1"

# ============================================================
# CACHE
# ============================================================
def get_cached_response(query):
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get(query.lower())
        except Exception:
            return None
    return None

def save_cached_response(query, response):
    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}
    cache[query.lower()] = response
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

# ============================================================
# FETCH MEDICAL INFO FROM NEW API
# ============================================================
def fetch_medical_info(query: str) -> dict:
    query_lower = query.lower()

    # 1️⃣ Check cache
    cached = get_cached_response(query_lower)
    if cached:
        return cached

    payload = {
        "message": query,
        "specialization": "general",
        "language": "en"
    }

    headers = {
        "Content-Type": "application/json",
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }

    for attempt in range(3):
        try:
            response = requests.post(BASE_URL, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()

            # ✅ Extract fields from structured response
            resp_obj = data.get("result", {}).get("response", {})

            description = resp_obj.get("message", "Not available")
            recommendations = resp_obj.get("recommendations", [])
            warnings = resp_obj.get("warnings", [])
            references = resp_obj.get("references", [])
            follow_up = resp_obj.get("followUp", [])

            result = {
                "query": query,
                "description": description,
                "common_symptoms": "; ".join(recommendations) if recommendations else "Not available",
                "treatment": "; ".join(follow_up) if follow_up else "Not available",
                "warnings": "; ".join(warnings) if warnings else "None",
                "references": "; ".join(references) if references else "None"
            }

            save_cached_response(query_lower, result)
            return result

        except Exception as e:
            print(f"Warning: Attempt {attempt + 1} failed: {e}")
            time.sleep(2)

    # ❌ API completely failed
    return {
        "query": query,
        "description": "Medical service unavailable",
        "common_symptoms": "Unavailable",
        "treatment": "Unavailable",
        "warnings": "Unavailable",
        "references": "Unavailable"
    }

# ============================================================
# RESPONSE
# ============================================================
def get_response(question: str, case_id: str = None) -> str:
    info = fetch_medical_info(question)

    reply = (
        f"🩺 Disease/Query: {info['query']}\n\n"
        f"📄 Description:\n{info['description']}\n\n"
        f"⚕️ Recommendations / Symptoms:\n{info['common_symptoms']}\n\n"
        f"💊 Follow-up / Treatment:\n{info['treatment']}\n\n"
        f"⚠️ Warnings:\n{info['warnings']}\n\n"
        f"📚 References:\n{info['references']}"
    )

    if case_id:
        add_message(case_id, "Dr. AI Assistant", reply)

    return reply
