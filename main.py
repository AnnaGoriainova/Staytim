from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class OnboardingData(BaseModel):
    business_name: str
    owner_name: str
    email: str
    business_type: str
    services: str
    prices: str = ""
    hours: str = ""
    location: str = ""
    personality: str = "friendly"
    special: str = ""
    phone: str = ""


class DemoChat(BaseModel):
    message: str
    history: list = []
    business_name: str = "Bella Studio"


def send_email(to: str, subject: str, body: str):
    """Send email via Zoho SMTP"""
    if not ZOHO_EMAIL or not ZOHO_PASSWORD:
        print("⚠️ No Zoho credentials — skipping email")
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = ZOHO_EMAIL
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP_SSL("smtp.zoho.com", 465) as server:
            server.login(ZOHO_EMAIL, ZOHO_PASSWORD)
            server.send_message(msg)
        print(f"✅ Email sent to {to}")
        return True
    except Exception as e:
        print(f"❌ Email failed: {e}")
        return False


@app.get("/")
def root():
    return {"status": "Staytim AI is running 🚀"}


@app.post("/onboarding")
async def onboarding(data: OnboardingData):
    """Handle new client signups"""
    print(f"\n🎉 NEW SIGNUP: {data.business_name} — {data.email}\n")

    # Save to business config
    add_business(data.phone or data.email, {
        "name": data.business_name,
        "type": data.business_type,
        "services": data.services,
        "prices": data.prices or data.services,
        "hours": data.hours or "Please contact us for hours",
        "location": data.location or "",
        "booking": "Reply to this message to book an appointment",
        "language": "English",
    })

    # Email YOU (notification)
    your_email_body = f"""
NEW STAYTIM SIGNUP! 🎉

Business: {data.business_name}
Type: {data.business_type}
Owner: {data.owner_name}
Email: {data.email}
Phone: {data.phone}
Location: {data.location}

Services: {data.services}
Hours: {data.hours}

ACTION NEEDED:
1. Reply to {data.email} within 24 hours
2. Set up their WhatsApp number in Twilio
3. Add their info to business_config.py
4. Send them their WhatsApp number to share with customers
"""
    send_email(ZOHO_EMAIL, f"🎉 New Signup: {data.business_name}", your_email_body)

    # Email the CLIENT (welcome)
    client_email_body = f"""Hi {data.owner_name},

Welcome to Staytim! We received your details for {data.business_name}.

Here's what happens next:

✅ Within 24 hours — We'll set up your AI assistant with your exact services and prices.

✅ You'll receive a WhatsApp number — Share it with your customers. They message it and your AI replies instantly.

✅ Your AI will handle — Customer inquiries 24/7, appointment bookings, follow-ups, and review requests.

If you have any questions, just reply to this email or message us at hello@staytim.io

Talk soon,
Anna
Staytim AI
hello@staytim.io | staytim.io
"""
    send_email(data.email, f"Welcome to Staytim — your AI is being set up! 🚀", client_email_body)

    return {"status": "success", "message": f"Welcome {data.business_name}!"}


@app.post("/demo/chat")
async def demo_chat(data: DemoChat):
    """Powers the demo chat on the website"""
    if not ANTHROPIC_API_KEY:
        return {"reply": "AI not configured yet."}

    system = f"""You are a friendly AI assistant for {data.business_name}.
You were set up through Staytim to handle customer inquiries 24/7.
Answer questions helpfully and professionally. Keep replies to 2-3 sentences max."""

    messages = data.history[-6:] if data.history else [{"role": "user", "content": data.message}]

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 200, "system": system, "messages": messages},
            timeout=30.0,
        )
    result = response.json()
    if "content" in result and result["content"]:
        return {"reply": result["content"][0]["text"]}
    return {"reply": "Sorry, something went wrong. Please try again."}


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """Receives incoming WhatsApp messages from Twilio"""
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
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 300, "system": system_prompt, "messages": [{"role": "user", "content": message}]},
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
            data={"From": f"whatsapp:{TWILIO_WHATSAPP_NUMBER}", "To": to_number, "Body": message},
        )
