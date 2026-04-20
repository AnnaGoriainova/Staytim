# Staytim AI Backend

FastAPI backend for Staytim — AI agents for small businesses.

## Setup

1. Create virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy and fill in your env:
```bash
cp .env.example .env
```

4. Run locally:
```bash
uvicorn main:app --reload
```

5. Test it:
```
http://localhost:8000
```

## Project Structure

- `main.py` — FastAPI app, WhatsApp webhook
- `business_config.py` — Business info for each client
- `requirements.txt` — Python dependencies
- `.env` — Your API keys (never commit this!)
