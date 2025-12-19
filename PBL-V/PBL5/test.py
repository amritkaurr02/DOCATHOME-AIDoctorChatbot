import requests

API_KEY = "adf6140c89msh16c85cb38a4c91ep1c941fjsn6ed1199558e3"
API_HOST = "ai-doctor-api-ai-medical-chatbot-healthcare-ai-assistant.p.rapidapi.com"
BASE_URL = f"https://{API_HOST}/chat?noqueue=1"

payload = {
    "message": "Tell me about Stiff Person Syndrome",
    "specialization": "general",  # optional, you can omit or use general
    "language": "en"
}

headers = {
    "Content-Type": "application/json",
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": API_HOST
}

response = requests.post(BASE_URL, json=payload, headers=headers)
print(response.status_code)
print(response.json())
