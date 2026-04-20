from fastapi import FastAPI, Request
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv
from pathlib import Path
from business_config import get_business_prompt, add_business

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

ZOHO_EMAIL = os.getenv("ZOHO_EMAIL")
ZOHO_PASSWORD = os.getenv("ZOHO_PASSWORD")

if ANTHROPIC_API_KEY:
    print(f"✅ Anthropic API Key loaded: {ANTHROPIC_API_KEY[:12]}...")
else:
    print("❌ ERROR: ANTHROPIC_API_KEY not found!")

app = FastAPI(title="Staytim AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://staytim.io", "https://www.staytim.io", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class OnboardingData(BaseModel):
    business_name: str
    owner_name: str
    email: str
    business_type: str
    services: str
    prices: str
    hours: str
    location: str
    personality: str = "friendly"
    special: str = ""
    phone: str = ""


@app.get("/")
def root():
    return {"status": "Staytim AI is running"}


@app.post("/onboarding")
async def onboarding(data: OnboardingData):
    print(f"NEW SIGNUP: {data.business_name} — {data.email}")
    add_business(data.phone or data.email, {
        "name": data.business_name,
        "type": data.business_type,
        "services": data.services,
        "prices": data.prices,
        "hours": data.hours,
        "location": data.location,
        "booking": "Reply to this message to book an appointment",
        "language": "English",
    })
    print(f"""
NEW STAYTIM SIGNUP!
Business: {data.business_name}
Owner: {data.owner_name}
Email: {data.email}
Phone: {data.phone}
Services: {data.services}
Hours: {data.hours}
""")
    return {"status": "success", "message": f"Welcome {data.business_name}!"}



class DemoChat(BaseModel):
    message: str
    history: list = []
    business_name: str = "Bella Studio"


@app.post("/demo/chat")
async def demo_chat(data: DemoChat):
    """Powers the demo chat on the website — no auth needed"""
    if not ANTHROPIC_API_KEY:
        return {"reply": "AI not configured yet."}

    system = f"""You are a friendly AI assistant for {data.business_name}.
You were set up through Staytim to handle customer inquiries 24/7.
Answer questions helpfully and professionally. Keep replies to 2-3 sentences max.
If asked about services or prices and you don't have specifics, give a helpful general answer
and suggest the customer contact the business directly for exact details."""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 200,
                "system": system,
                "messages": data.history[-6:] if data.history else [{"role": "user", "content": data.message}],
            },
            timeout=30.0,
        )
    result = response.json()
    if "content" in result and result["content"]:
        return {"reply": result["content"][0]["text"]}
    return {"reply": "Sorry, something went wrong. Please try again."}

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    form_data = await request.form()
    incoming_msg = form_data.get("Body", "").strip()
    from_number = form_data.get("From", "")
    business_id = form_data.get("To", "").replace("whatsapp:", "")

    if not incoming_msg:
        return PlainTextResponse("", status_code=200)

    reply = await get_ai_reply(incoming_msg, from_number, business_id)

    if TWILIO_ACCOUNT_SID and TWILIO_ACCOUNT_SID != "placeholder":
        await send_whatsapp_message(from_number, reply)

    return {"reply": reply, "to": from_number}


async def get_ai_reply(message: str, customer_number: str, business_id: str) -> str:
    if not ANTHROPIC_API_KEY:
        return "Error: ANTHROPIC_API_KEY not set"

    system_prompt = get_business_prompt(business_id)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 300,
                "system": system_prompt,
                "messages": [{"role": "user", "content": message}],
            },
            timeout=30.0,
        )

    data = response.json()
    if "content" in data and data["content"]:
        return data["content"][0]["text"]
    return "Hi! Thanks for your message. We'll get back to you shortly."


async def send_whatsapp_message(to_number: str, message: str):
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json",
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            data={
                "From": f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
                "To": to_number,
                "Body": message,
            },
        )
