"""Intent classification (no LLM): TF-IDF features + logistic regression, plus keyword rules."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

log = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "intents.yml"
PLACEHOLDER_NAMES = ["bag", "belt", "shoe", "dress", "wallet", "sandals", "it"]

# High-precision keyword rules. They win only when the model is unsure.
KEYWORD_RULES: list[tuple[str, str]] = [
    (r"\b(how much|price|cost|wetin be the price)\b", "price"),
    (r"\b(available|in stock|out of stock|still dey|una get)\b", "availability"),
    (r"\b(pic|pics|picture|pictures|photo|photos|image|images)\b", "images"),
    (r"\b(deliver|delivery|ship|shipping|dispatch)\b", "delivery"),
    (r"\b(track|my order|order status)\b", "order_status"),
    (r"\b(buy|order|purchase|link|pay|checkout)\b", "purchase"),
    (r"\b(human|agent|person|customer care|complain)\b", "human_agent"),
    (r"^(hi|hello|hey|good (morning|afternoon|evening)|how far)\b", "greeting"),
    (r"\b(thank|thanks)\b", "thanks"),
]


@dataclass
class IntentResult:
    intent: str
    confidence: float
    source: str  # "model" or "rule" or "fallback"


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s']", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class IntentClassifier:
    def __init__(self, data_path: Path = DATA_PATH, threshold: float = 0.35):
        self.data_path = data_path
        self.threshold = threshold
        self.pipeline: Pipeline | None = None

    def _load_examples(self, product_names: list[str]) -> tuple[list[str], list[str]]:
        with open(self.data_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        names = [n.lower() for n in product_names if n] or PLACEHOLDER_NAMES
        names = list(dict.fromkeys(names + PLACEHOLDER_NAMES))
        texts, labels = [], []
        for intent, examples in data.items():
            for ex in examples or []:
                ex = str(ex)
                if "[product]" in ex:
                    # expand each template with a few product names
                    for name in names[:6]:
                        texts.append(normalize(ex.replace("[product]", name)))
                        labels.append(intent)
                else:
                    texts.append(normalize(ex))
                    labels.append(intent)
        return texts, labels

    def train(self, product_names: list[str] | None = None) -> None:
        texts, labels = self._load_examples(product_names or [])
        features = FeatureUnion([
            ("words", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True)),
            ("chars", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True)),
        ])
        self.pipeline = Pipeline([
            ("features", features),
            ("clf", LogisticRegression(max_iter=2000, C=10, class_weight="balanced")),
        ])
        self.pipeline.fit(texts, labels)
        log.info("Intent model trained on %d examples, %d intents", len(texts), len(set(labels)))

    def _rule_intent(self, text: str) -> str | None:
        for pattern, intent in KEYWORD_RULES:
            if re.search(pattern, text):
                return intent
        return None

    def predict(self, message: str) -> IntentResult:
        if self.pipeline is None:
            self.train()
        text = normalize(message)
        if not text:
            return IntentResult("unknown", 0.0, "fallback")

        probs = self.pipeline.predict_proba([text])[0]
        classes = self.pipeline.classes_
        best = probs.argmax()
        intent, conf = classes[best], float(probs[best])

        if conf >= self.threshold:
            return IntentResult(intent, conf, "model")

        rule = self._rule_intent(text)
        if rule:
            return IntentResult(rule, max(conf, self.threshold), "rule")
        return IntentResult(intent, conf, "model")
