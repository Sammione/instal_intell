"""Fetches and caches the product catalog from the backend API."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict, dataclass, field

import httpx

from .config import settings

log = logging.getLogger(__name__)


@dataclass
class Product:
    id: str
    name: str
    slug: str
    description: str
    category: str
    brand: str
    price: float
    currency: str
    quantity: int
    in_stock: bool
    images: list[str] = field(default_factory=list)
    link: str = ""

    @classmethod
    def from_api(cls, d: dict) -> "Product":
        return cls(
            id=str(d.get("id", "")),
            name=(d.get("productName") or "").strip(),
            slug=d.get("slug") or "",
            description=d.get("description") or "",
            category=d.get("category") or "",
            brand=d.get("brand") or "",
            price=float(d.get("price") or 0),
            currency=d.get("currency") or "NGN",
            quantity=int(d.get("quantity") or 0),
            in_stock=bool(d.get("inStock", False)),
            images=list(d.get("productImages") or []),
            link=d.get("productLink") or "",
        )

    @property
    def has_category(self) -> bool:
        return bool(self.category) and self.category.lower() != "unassigned"

    @property
    def search_text(self) -> str:
        parts = [self.name, self.description, self.brand]
        if self.has_category:
            parts.append(self.category)
        return " ".join(p for p in parts if p)


class Catalog:
    def __init__(self, fetcher=None):
        self._products: list[Product] = []
        self._loaded_at = 0.0
        self._lock = threading.Lock()
        self._fetcher = fetcher or self._fetch_from_api
        self.version = 0  # bumps whenever products change, so search indexes rebuild

    def _fetch_from_api(self) -> list[dict]:
        headers = {"Accept": "application/json"}
        if settings.products_api_key:
            headers["Authorization"] = f"Bearer {settings.products_api_key}"
        resp = httpx.get(settings.products_api_url, headers=headers,
                         timeout=settings.request_timeout_seconds)
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("success", True):
            raise RuntimeError(f"Products API returned success=false: {payload}")
        return payload.get("data", [])

    def refresh(self, force: bool = False) -> None:
        with self._lock:
            is_fresh = time.time() - self._loaded_at < settings.catalog_refresh_seconds
            if is_fresh and not force and self._loaded_at:
                return
            try:
                raw = self._fetcher()
                products = [Product.from_api(p) for p in raw if p.get("productName")]
                if [asdict(p) for p in products] != [asdict(p) for p in self._products]:
                    self.version += 1
                self._products = products
                self._loaded_at = time.time()
                log.info("Catalog loaded: %d products", len(products))
            except Exception as exc:  # keep serving stale data if the API is down
                log.error("Catalog refresh failed: %s", exc)
                if not self._loaded_at:
                    raise

    @property
    def products(self) -> list[Product]:
        self.refresh()
        return self._products

    def get(self, product_id: str) -> Product | None:
        return next((p for p in self.products if p.id == product_id), None)
