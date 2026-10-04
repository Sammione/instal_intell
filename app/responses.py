"""Reply templates. Edit wording here; the logic never invents product facts."""
from __future__ import annotations

import random

from .catalog import Product
from .config import settings

CURRENCY_SYMBOLS = {"NGN": "₦", "USD": "$", "GBP": "£", "EUR": "€"}


def money(p: Product) -> str:
    symbol = CURRENCY_SYMBOLS.get(p.currency.upper(), p.currency + " ")
    amount = int(p.price) if float(p.price).is_integer() else p.price
    return f"{symbol}{amount:,}"


def greeting() -> str:
    return random.choice([
        f"Hi there 👋 Welcome to {settings.store_name}! Ask me about any product: price, availability, photos or how to order.",
        f"Hello! 😊 Thanks for reaching out to {settings.store_name}. What are you looking for today?",
    ])


def thanks() -> str:
    return random.choice(["You're welcome! 😊 Anything else I can help with?",
                          "My pleasure! Let me know if you need anything else."])


def goodbye() -> str:
    return "Thanks for chatting with us! Come back anytime. 👋"


def price(p: Product) -> str:
    stock = "and it's in stock ✅" if p.in_stock and p.quantity > 0 else "but it's currently out of stock ❌"
    return f"The {p.name} is {money(p)}, {stock}"


def availability(p: Product) -> str:
    if p.in_stock and p.quantity > 0:
        left = f" Only {p.quantity} left!" if p.quantity <= 5 else ""
        return f"Yes, the {p.name} is available ✅{left} It's {money(p)}."
    return f"Sorry, the {p.name} is currently out of stock ❌. Would you like me to show you something similar?"


def product_info(p: Product) -> str:
    lines = [f"*{p.name}*"]
    if p.description:
        lines.append(p.description)
    if p.brand:
        lines.append(f"Brand: {p.brand}")
    if p.has_category:
        lines.append(f"Category: {p.category}")
    lines.append(f"Price: {money(p)}")
    lines.append("In stock ✅" if p.in_stock and p.quantity > 0 else "Out of stock ❌")
    return "\n".join(lines)


def images(p: Product) -> str:
    if p.images:
        return f"Here's the {p.name} 📸"
    return f"I don't have photos of the {p.name} yet. A team member can send some. 🙏"


def purchase(p: Product) -> str:
    if not (p.in_stock and p.quantity > 0):
        return f"The {p.name} is out of stock at the moment, sorry. Want to see other options?"
    link = f" You can order it here: {p.link}" if p.link else ""
    return f"Great choice! The {p.name} is {money(p)}.{link}"


def product_list(products: list[Product], intro: str | None = None) -> str:
    shown = products[: settings.max_products_in_list]
    lines = [intro or "Here's what we have:"]
    for p in shown:
        status = "" if p.in_stock and p.quantity > 0 else " (out of stock)"
        lines.append(f"• {p.name}: {money(p)}{status}")
    if len(products) > len(shown):
        lines.append(f"…and {len(products) - len(shown)} more. Tell me what you're looking for!")
    else:
        lines.append("Which one would you like to know more about?")
    return "\n".join(lines)


def which_product(products: list[Product]) -> str:
    return product_list(products, intro="Which product do you mean?")


def ask_product() -> str:
    return "Which product are you asking about? You can tell me the name. 🙂"


def no_match() -> str:
    return "Sorry, I couldn't find that product 🤔 Type *catalog* to see everything we have."


def empty_catalog() -> str:
    return "Our catalog is being updated right now. A team member will get back to you shortly 🙏"


def delivery() -> str:
    return "Good question! A team member will confirm delivery options and fees for your location shortly 🚚"


def order_status() -> str:
    return "I'm passing this to our team so they can check your order. Please share your order number or the name used to order 🙏"


def human_agent() -> str:
    return "No problem, I'm connecting you with a team member now. They'll reply here shortly 🙏"


def fallback() -> str:
    return ("Sorry, I didn't quite get that 🤔 You can ask me things like:\n"
            "• How much is the belt?\n• Is it available?\n• Send pictures\n• What do you sell?")
