"""Tests run against a fake catalog, so they never hit the network."""
import pytest

from app.catalog import Catalog
from app.engine import Engine

FAKE = [
    {"id": "1", "productName": "Belt", "slug": "belt",
     "description": "Handmade leather belt", "category": "Unassigned",
     "brand": "Thanice Clothing", "price": 2000, "currency": "NGN",
     "quantity": 4, "inStock": True,
     "productImages": ["https://example.com/belt.webp"],
     "productLink": "https://aba-craft.vercel.app/dashboard/products/belt"},
    {"id": "2", "productName": "Leather Tote Bag", "slug": "leather-tote-bag",
     "description": "Spacious handmade leather tote for work", "category": "Bags",
     "brand": "Thanice Clothing", "price": 18500, "currency": "NGN",
     "quantity": 0, "inStock": False, "productImages": [],
     "productLink": "https://aba-craft.vercel.app/dashboard/products/leather-tote-bag"},
]


@pytest.fixture(scope="module")
def engine():
    e = Engine(catalog=Catalog(fetcher=lambda: FAKE))
    e.warmup()
    return e


def test_price(engine):
    a = engine.answer("How much is the belt?", "u1")
    assert a.intent == "price"
    assert "2,000" in a.reply


def test_availability_out_of_stock(engine):
    a = engine.answer("is the leather tote bag available?", "u2")
    assert a.intent == "availability"
    assert "out of stock" in a.reply.lower()


def test_followup_uses_memory(engine):
    engine.answer("how much is the tote bag", "u3")
    a = engine.answer("is it available?", "u3")
    assert "Tote" in a.reply


def test_typo_still_matches(engine):
    a = engine.answer("how much for the lether tote bg", "u4")
    assert "18,500" in a.reply


def test_semantic_search(engine):
    a = engine.answer("do you have anything handmade leather", "u5")
    assert a.products


def test_list_products(engine):
    a = engine.answer("what do you sell", "u6")
    assert "Belt" in a.reply and "Tote" in a.reply


def test_delivery_handoff(engine):
    a = engine.answer("do you deliver to abuja?", "u7")
    assert a.handoff is True


def test_order_status_handoff(engine):
    a = engine.answer("where is my order", "u8")
    assert a.handoff is True


def test_greeting(engine):
    a = engine.answer("hello", "u9")
    assert a.intent == "greeting"


def test_gibberish_handoff(engine):
    a = engine.answer("qwrtyp zxcvb mnbvc", "u10")
    assert a.handoff is True


def test_purchase_link(engine):
    a = engine.answer("i want to buy the belt", "u11")
    assert "aba-craft.vercel.app" in a.reply
