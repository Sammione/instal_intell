"""Finds which product(s) a message is about: fuzzy name matching + TF-IDF semantic search."""
from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .catalog import Catalog, Product
from .config import settings
from .nlu import normalize

STOPWORDS = {
    "a", "an", "the", "is", "it", "this", "that", "do", "you", "have", "i", "me", "my",
    "of", "for", "to", "in", "on", "and", "or", "please", "pls", "abeg", "how", "much",
    "what", "price", "available", "want", "buy", "send", "show", "can", "get", "una",
    "your", "any", "still", "one", "some", "something", "looking", "need", "are", "there",
    "tell", "about", "more", "with", "sell", "stock", "picture", "pictures", "pics",
    "order", "link", "dey", "be", "wetin", "much", "cost", "see",
}


@dataclass
class Match:
    product: Product
    score: float
    method: str  # "fuzzy" or "semantic"


def _ngrams(tokens: list[str], max_n: int = 4) -> list[str]:
    out = []
    for n in range(1, max_n + 1):
        for i in range(len(tokens) - n + 1):
            out.append(" ".join(tokens[i:i + n]))
    return out


class ProductMatcher:
    def __init__(self, catalog: Catalog):
        self.catalog = catalog
        self._index_version = -1
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None
        self._indexed: list[Product] = []

    # ---------- indexing ----------
    def _ensure_index(self) -> None:
        products = self.catalog.products
        if self._index_version == self.catalog.version and self._indexed:
            return
        self._indexed = list(products)
        if products:
            self._vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                               sublinear_tf=True)
            self._matrix = self._vectorizer.fit_transform(
                [normalize(p.search_text) for p in products])
        self._index_version = self.catalog.version

    # ---------- fuzzy name matching ----------
    def _fuzzy(self, text: str) -> list[Match]:
        tokens = [t for t in text.split() if t not in STOPWORDS and len(t) > 1]
        if not tokens:
            return []
        grams = _ngrams(tokens)
        matches = []
        for p in self._indexed:
            names = {normalize(p.name), normalize(p.slug.replace("-", " "))}
            best = 0.0
            for name in names:
                if not name:
                    continue
                if re.search(rf"\b{re.escape(name)}s?\b", text):
                    best = 100.0
                    break
                for g in grams:
                    best = max(best, fuzz.ratio(g, name))
            if best >= settings.product_match_threshold:
                matches.append(Match(p, best, "fuzzy"))
        return sorted(matches, key=lambda m: m.score, reverse=True)

    # ---------- semantic (descriptions, brand, category) ----------
    def _semantic(self, text: str) -> list[Match]:
        if self._vectorizer is None or not self._indexed:
            return []
        content = " ".join(t for t in text.split() if t not in STOPWORDS)
        if not content:
            return []
        sims = cosine_similarity(self._vectorizer.transform([content]), self._matrix)[0]
        matches = [Match(p, float(s), "semantic")
                   for p, s in zip(self._indexed, sims)
                   if s >= settings.semantic_match_threshold]
        return sorted(matches, key=lambda m: m.score, reverse=True)

    def find(self, message: str, allow_semantic: bool = True) -> list[Match]:
        self._ensure_index()
        text = normalize(message)
        matches = self._fuzzy(text)
        if matches:
            top = matches[0].score
            return [m for m in matches if m.score >= top - 5]  # keep near-ties
        if allow_semantic:
            return self._semantic(text)[: settings.max_products_in_list]
        return []
