from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import httpx
import os
from dotenv import load_dotenv
from pathlib import Path
from business_config import get_business_prompt

# Load .env from same folder as this file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

# Debug on startup - shows in terminal
if ANTHROPIC_API_KEY:
    print(f"✅ Anthropic API Key loaded: {ANTHROPIC_API_KEY[:12]}...")
else:
    print("❌ ERROR: ANTHROPIC_API_KEY not found in .env file!")

app = FastAPI(title="Staytim AI Backend")


@app.get("/")
def root():
    return {"status": "Staytim AI is running"}


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """Receives incoming WhatsApp messages from Twilio"""
    form_data = await request.form()

    incoming_msg = form_data.get("Body", "").strip()
    from_number = form_data.get("From", "")
    business_id = form_data.get("To", "").replace("whatsapp:", "")

    if not incoming_msg:
        return PlainTextResponse("", status_code=200)

    # Get AI reply
    reply = await get_ai_reply(incoming_msg, from_number, business_id)

    # Send reply via Twilio (skip if no Twilio keys yet)
    if TWILIO_ACCOUNT_SID and TWILIO_ACCOUNT_SID != "placeholder":
        await send_whatsapp_message(from_number, reply)

    # Return reply in response so we can test without Twilio
    return {"reply": reply, "to": from_number}


async def get_ai_reply(message: str, customer_number: str, business_id: str) -> str:
    """Get AI reply from Claude"""
    if not ANTHROPIC_API_KEY:
        return "Error: ANTHROPIC_API_KEY not set in .env file"

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
                "messages": [
                    {"role": "user", "content": message}
                ],
            },
            timeout=30.0,
        )

    data = response.json()
    if "content" in data and data["content"]:
        return data["content"][0]["text"]
    return "Hi! Thanks for your message. We'll get back to you shortly."


async def send_whatsapp_message(to_number: str, message: str):
    """Send WhatsApp message via Twilio"""
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
