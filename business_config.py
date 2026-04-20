"""
Business configuration - stores info about each client business
so the AI knows exactly what to say about their services,
prices, hours, and location.
"""

# In production this will come from a database (Supabase)
# For now it's a simple dictionary

BUSINESSES = {
    # Key = Twilio phone number assigned to this business
    "default": {
        "name": "Our Business",
        "type": "salon",
        "services": "haircuts, coloring, styling",
        "prices": "starting from $30",
        "hours": "Mon-Sat 10am-8pm",
        "location": "123 Main Street",
        "booking": "Call us or reply to this message to book",
        "language": "English",
    },
    # Example: Add a real client like this
    # "+14155551234": {
    #     "name": "Bella Studio",
    #     "type": "beauty salon",
    #     "services": "haircuts, balayage, keratin treatment, manicure, pedicure",
    #     "prices": "Haircut $45, Balayage from $120, Keratin $200, Mani $35, Pedi $45",
    #     "hours": "Tue-Sat 10am-7pm, Sun 11am-5pm, Closed Monday",
    #     "location": "456 Oak Ave, San Mateo CA",
    #     "booking": "Reply with your preferred date and service to book",
    #     "language": "English",
    # },
}


def get_business_prompt(business_id: str) -> str:
    """Build system prompt for a specific business"""
    # Try to find by business ID, fall back to default
    business = BUSINESSES.get(business_id, BUSINESSES["default"])

    return f"""You are a friendly AI assistant for {business['name']}, a {business['type']}.

YOUR JOB:
- Answer customer questions instantly and professionally
- Help customers book appointments
- Share information about services and prices
- Always be warm, helpful, and concise (max 3 sentences per reply)

BUSINESS INFO:
- Name: {business['name']}
- Services: {business['services']}
- Prices: {business['prices']}
- Hours: {business['hours']}
- Location: {business['location']}
- How to book: {business['booking']}

RULES:
- Always reply in {business['language']}
- Never make up prices or services not listed above
- If you don't know something, say "Let me check that for you - please call us at [number]"
- Keep replies SHORT - this is WhatsApp, not email
- End with a helpful call to action when relevant

You represent this business professionally. Be warm but efficient."""


def add_business(phone_number: str, business_data: dict):
    """Add a new business client (will connect to DB later)"""
    BUSINESSES[phone_number] = business_data
    return {"status": "added", "business": business_data["name"]}
