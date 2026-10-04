"""The intelligence: turns a message into a reply using intent + product match + database."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from . import responses as R
from .catalog import Catalog, Product
from .config import settings
from .matcher import ProductMatcher
from .memory import ConversationMemory
from .nlu import IntentClassifier

log = logging.getLogger(__name__)

# Intents that need to know WHICH product the customer means
PRODUCT_INTENTS = {"price", "availability", "product_info", "images", "purchase"}
# Intents a bot should never try to answer from the catalog alone
HANDOFF_INTENTS = {"order_status", "human_agent", "delivery"}
SMALLTALK = {"greeting", "thanks", "goodbye"}


@dataclass
class Answer:
    reply: str
    intent: str
    confidence: float
    handoff: bool = False
    products: list[dict] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    source: str = "model"


def _product_payload(p: Product) -> dict:
    return {
        "id": p.id, "name": p.name, "price": p.price, "currency": p.currency,
        "in_stock": p.in_stock, "quantity": p.quantity, "link": p.link,
        "images": p.images,
    }


class Engine:
    def __init__(self, catalog: Catalog | None = None):
        self.catalog = catalog or Catalog()
        self.matcher = ProductMatcher(self.catalog)
        self.memory = ConversationMemory()
        self.classifier = IntentClassifier(threshold=settings.intent_confidence_threshold)
        self._trained = False

    def warmup(self) -> None:
        try:
            self.catalog.refresh(force=True)
            names = [p.name for p in self.catalog.products]
        except Exception:
            names = []
        self.classifier.train(names)
        self._trained = True

    def retrain(self) -> None:
        self.catalog.refresh(force=True)
        self.classifier.train([p.name for p in self.catalog.products])

    # ------------------------------------------------------------------
    def answer(self, message: str, user_id: str = "anonymous") -> Answer:
        if not self._trained:
            self.warmup()

        result = self.classifier.predict(message)
        intent, conf, source = result.intent, result.confidence, result.source

        # Unsure and no keyword rule fired -> don't guess, ask and flag for a human.
        if source == "model" and conf < settings.intent_confidence_threshold:
            return Answer(R.fallback(), "unknown", conf, handoff=True, source="fallback")

        try:
            products = self.catalog.products
        except Exception as exc:
            log.error("Catalog unavailable: %s", exc)
            return Answer(R.empty_catalog(), intent, conf, handoff=True, source=source)

        if not products:
            return Answer(R.empty_catalog(), intent, conf, handoff=True, source=source)

        # 1. Small talk
        if intent in SMALLTALK:
            text = {"greeting": R.greeting, "thanks": R.thanks, "goodbye": R.goodbye}[intent]()
            return Answer(text, intent, conf, source=source)

        # 2. Things only a human can answer
        if intent in HANDOFF_INTENTS:
            text = {"delivery": R.delivery, "order_status": R.order_status,
                    "human_agent": R.human_agent}[intent]()
            return Answer(text, intent, conf, handoff=True, source=source)

        # 3. Browse the catalog
        if intent == "list_products":
            self.memory.set_last_products(user_id, [p.id for p in products])
            return Answer(R.product_list(products), intent, conf,
                          products=[_product_payload(p) for p in products[:settings.max_products_in_list]],
                          source=source)

        # 4. Open-ended search ("something in leather")
        if intent == "search":
            matches = self.matcher.find(message)
            if not matches:
                return Answer(R.product_list(products, "I couldn't find an exact match, but here's what we have:"),
                              intent, conf,
                              products=[_product_payload(p) for p in products[:settings.max_products_in_list]],
                              source=source)
            found = [m.product for m in matches]
            self.memory.set_last_products(user_id, [p.id for p in found])
            return Answer(R.product_list(found, "Here's what I found:"), intent, conf,
                          products=[_product_payload(p) for p in found], source=source)

        # 5. Questions about a specific product
        if intent in PRODUCT_INTENTS:
            matches = self.matcher.find(message)
            found = [m.product for m in matches]

            if not found:  # fall back to the product we were just discussing
                remembered = [self.catalog.get(pid) for pid in self.memory.get_last_products(user_id)]
                found = [p for p in remembered if p]
                if len(found) > 1:
                    return Answer(R.which_product(found), intent, conf,
                                  products=[_product_payload(p) for p in found], source=source)

            if not found:
                if len(products) == 1:  # tiny catalog: no ambiguity possible
                    found = products
                else:
                    return Answer(R.ask_product(), intent, conf, source=source)

            if len(found) > 1:
                self.memory.set_last_products(user_id, [p.id for p in found])
                return Answer(R.which_product(found), intent, conf,
                              products=[_product_payload(p) for p in found], source=source)

            product = found[0]
            self.memory.set_last_products(user_id, [product.id])
            text = {
                "price": R.price, "availability": R.availability,
                "product_info": R.product_info, "images": R.images, "purchase": R.purchase,
            }[intent](product)
            return Answer(text, intent, conf, products=[_product_payload(product)],
                          images=product.images if intent == "images" else [], source=source)

        # 6. Unclear -> clarify and flag for a human
        low = conf < settings.intent_confidence_threshold
        return Answer(R.fallback(), intent if not low else "unknown", conf,
                      handoff=low, source=source)
