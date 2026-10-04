# Aba Craft Instagram Assistant

A product Q&A "intelligence" for Instagram DMs that answers from your live catalog at
`https://aba-craft.vercel.app/api/products` — **without an LLM**. Nothing is generated;
every reply is a template filled with real data, so it can never invent a price or a stock level.

## How it works

```
Instagram DM
   ↓ (the automation workflow — not this service)
POST /ask  { "message": "...", "user_id": "..." }
   ↓
1. Intent classifier     TF-IDF + logistic regression  → price / availability / images / ...
2. Product matcher       rapidfuzz (typos) + TF-IDF char n-grams (vague questions)
3. Conversation memory   remembers the last product, so "is it available?" works
4. Catalog lookup        cached fetch from the products API
5. Reply template        filled with real data
   ↓
{ "reply": "...", "intent": "price", "confidence": 0.94, "handoff": false, "products": [...] }
```

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Open <http://localhost:8000/docs> for interactive API docs.

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"message": "how much is the belt?", "user_id": "ig_12345"}'
```

```json
{
  "reply": "The Belt is ₦2,000, and it's in stock ✅",
  "intent": "price",
  "confidence": 0.94,
  "handoff": false,
  "products": [{"id": "6a19...", "name": "Belt", "price": 2000, "currency": "NGN",
                "in_stock": true, "quantity": 4, "link": "https://aba-craft.vercel.app/...",
                "images": ["https://res.cloudinary.com/..."]}],
  "images": [],
  "source": "model"
}
```

With Docker:

```bash
docker build -t aba-craft-assistant .
docker run -p 8000:8000 --env-file .env aba-craft-assistant
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/ask` | Main endpoint. Message in, reply out. |
| GET | `/health` | Liveness + how many products are loaded. |
| GET | `/products` | The cached catalog as this service sees it. |
| POST | `/admin/refresh` | Re-fetch the catalog immediately. Call from your backend when products change. |
| POST | `/admin/retrain` | Reload `data/intents.yml` and retrain, with no redeploy. |
| DELETE | `/memory/{user_id}` | Forget a user's conversation context. |

Set `SERVICE_API_KEY` in `.env` to require an `X-API-Key` header on every endpoint except `/health`.

## For the automation person

Their workflow needs to:

1. `POST` each incoming DM to `https://<your-host>/ask` with `message` and `user_id`
   (use the Instagram sender ID as `user_id` so follow-up questions work).
2. Send `reply` back to the user.
3. If `handoff` is `true`, notify a human instead of (or as well as) replying.
4. Optionally send the URLs in `images` as photo attachments.

Nothing else is required from them. This service never talks to Instagram directly.

## Intents it handles

`greeting` · `thanks` · `goodbye` · `price` · `availability` · `product_info` · `images` ·
`purchase` · `list_products` · `search` · `delivery`\* · `order_status`\* · `human_agent`\*

\* always returns `handoff: true` — these need a human.

## Making it smarter

The single highest-value thing you can do is **add real customer questions** to
`data/intents.yml` under the right intent, then call `POST /admin/retrain`.
Export the last few hundred DMs from your Instagram inbox and label them. Include the
Pidgin, slang and typos exactly as customers write them — the character n-gram features
are what let it survive "lether bg".

Then run the service in shadow mode for a week: log every message with its predicted
intent and confidence, review the low-confidence ones, and add them as training examples.
Accuracy climbs fast with real data.

### Tuning

| Setting | Effect |
|---|---|
| `INTENT_CONFIDENCE_THRESHOLD` | Raise it for fewer wrong answers and more handoffs; lower it for the reverse. |
| `PRODUCT_MATCH_THRESHOLD` | 0–100 fuzzy score. Raise if the wrong product gets matched. |
| `SEMANTIC_MATCH_THRESHOLD` | Cosine similarity for vague searches. Raise for stricter results. |
| `CATALOG_REFRESH_SECONDS` | How stale prices can get. Also call `/admin/refresh` on product changes. |

### Optional upgrades

- **Better semantic search:** swap the TF-IDF matcher in `app/matcher.py` for
  `sentence-transformers` with `all-MiniLM-L6-v2`. It's still not an LLM — it only turns
  text into vectors — but it understands meaning much better. Costs ~90 MB of RAM.
- **Shared memory:** replace the in-process dict in `app/memory.py` with Redis once you
  run more than one worker, otherwise follow-ups break across processes.
- **Delivery answers:** once the backend exposes shipping zones and fees, replace the
  handoff in `app/responses.py:delivery()` with a real lookup.
- **Order status:** the same, once there's an orders endpoint you can query by phone or order number.

## Tests

```bash
pytest -q
```

Tests run against a fake catalog, so they never hit the network.

## Project layout

```
app/
  config.py      settings from environment
  catalog.py     fetches + caches products, serves stale data if the API is down
  nlu.py         intent classifier (TF-IDF + logistic regression) and keyword rules
  matcher.py     product matching: fuzzy names + semantic search
  memory.py      per-user short-term memory with TTL
  responses.py   all reply wording lives here
  engine.py      ties it together and decides when to hand off
  main.py        FastAPI endpoints
data/intents.yml training examples — the file you grow over time
tests/           end-to-end tests on a fake catalog
```

## Notes

- Products with the category `Unassigned` have that field hidden in replies.
- The catalog cache keeps serving the last good copy if the products API goes down, so
  the bot stays useful during a backend outage.
- `/products` and the `/admin/*` routes should not be publicly reachable in production —
  set `SERVICE_API_KEY` or put them behind your network.
