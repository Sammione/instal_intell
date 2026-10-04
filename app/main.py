"""FastAPI service the Instagram automation workflow calls."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .config import settings
from .engine import Engine

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("assistant")

engine = Engine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        engine.warmup()
    except Exception as exc:
        log.error("Warmup failed (service will retry per request): %s", exc)
    yield


app = FastAPI(
    title="Aba Craft Instagram Assistant",
    description="Rule + ML product Q&A over the Aba Craft catalog. No LLM.",
    version="1.0.0",
    lifespan=lifespan,
)


def require_key(x_api_key: str | None = Header(default=None)):
    if settings.service_api_key and x_api_key != settings.service_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


class AskRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000,
                         examples=["How much is the belt?"])
    user_id: str = Field(default="anonymous", max_length=128,
                         examples=["instagram_17841400000000000"])


class ProductOut(BaseModel):
    id: str
    name: str
    price: float
    currency: str
    in_stock: bool
    quantity: int
    link: str
    images: list[str]


class AskResponse(BaseModel):
    reply: str
    intent: str
    confidence: float
    handoff: bool
    products: list[ProductOut] = []
    images: list[str] = []
    source: str


@app.get("/health")
def health():
    try:
        count = len(engine.catalog.products)
        return {"status": "ok", "products": count, "catalog_version": engine.catalog.version}
    except Exception as exc:
        return {"status": "degraded", "error": str(exc)}


@app.post("/ask", response_model=AskResponse, dependencies=[Depends(require_key)])
def ask(req: AskRequest):
    """Main endpoint: give it a customer message, get a reply back."""
    answer = engine.answer(req.message, req.user_id)
    log.info("user=%s intent=%s conf=%.2f handoff=%s msg=%r",
             req.user_id, answer.intent, answer.confidence, answer.handoff, req.message)
    return AskResponse(
        reply=answer.reply, intent=answer.intent, confidence=round(answer.confidence, 3),
        handoff=answer.handoff, products=answer.products, images=answer.images,
        source=answer.source,
    )


@app.get("/products", dependencies=[Depends(require_key)])
def products():
    return {"count": len(engine.catalog.products),
            "products": [p.__dict__ for p in engine.catalog.products]}


@app.post("/admin/refresh", dependencies=[Depends(require_key)])
def refresh():
    """Re-fetch the catalog now (call this from your backend when products change)."""
    engine.catalog.refresh(force=True)
    return {"status": "refreshed", "products": len(engine.catalog.products)}


@app.post("/admin/retrain", dependencies=[Depends(require_key)])
def retrain():
    """Reload data/intents.yml and retrain, after you add new training examples."""
    engine.retrain()
    return {"status": "retrained"}


@app.delete("/memory/{user_id}", dependencies=[Depends(require_key)])
def clear_memory(user_id: str):
    engine.memory.clear(user_id)
    return {"status": "cleared", "user_id": user_id}
