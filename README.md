# MGC Developments — Build Task Submission

Four parts, one repo.

```
docs/                               ← repo root = Part 1 + Part 4
├── README.md                       ← you are here
├── app.py                          ← Part 1: CLI document assistant
├── streamlit_app.py                ← Part 4: web version (also has the Part 3 lead-scoring tab)
├── rag.py
├── ingest.py
├── 01_mgc_aurora_heights_brochure.md
├── 02_price_list_payment_plan.md
├── 03_booking_policy_faq.md
├── lead_model.pkl                  ← copy of the trained model, used by streamlit_app.py
├── .env                            ← GEMINI_API_KEY=... (not committed)
├── part2_database/
│   ├── schema.sql
│   ├── queries.sql
│   ├── run_queries.py              ← optional: verifies the queries against leads.csv
│   └── leads.csv
└── part3_ML_Task/
    ├── train.py
    ├── leads.csv
    └── lead_model.pkl              ← produced by train.py
```

---

## Part 1 — Document Assistant

Answers salesperson questions about MGC Aurora Heights using only the 3
provided documents (brochure, price list, booking policy FAQ), with the
source cited on every claim. Retrieval is TF-IDF + cosine similarity over
section-chunked documents; generation is Gemini (`gemini-2.5-flash`) with a
strict grounding system prompt that:
- forces every factual claim to cite its source document + section
- refuses to guess when retrieval confidence is low
- states both values and refuses to pick one when documents conflict
  (e.g. the transfer fee: 2% vs 2.5%)
- preserves "unconfirmed" / "pending" status instead of upgrading it to fact

**Run (CLI), from the `docs/` folder:**
```
pip install pandas scikit-learn google-genai python-dotenv
```
Create a `.env` file in `docs/`:
```
GEMINI_API_KEY=your_key_here
```
Then:
```
python app.py
```
Or ask one question directly: `python app.py "What's the transfer fee?"`

**Sanity-check retrieval alone (no API key needed):**
```
python rag.py
```

---

## Part 2 — Database

In `part2_database/`: `schema.sql` and `queries.sql` — see comments inside
each file for reasoning.

**Key decision:** the raw CSV's `lead_id` is always unique, so it's *not*
the duplicate marker. `crm_record_hash` is — 160 leads in the data are
entered twice under two different `lead_id`s (same hash, identical
details). The schema puts a `UNIQUE` constraint on `crm_record_hash` to
stop that at the database level going forward.

**To verify the queries actually work** (optional, no server needed —
uses Python's built-in `sqlite3`):
```
cd part2_database
python run_queries.py
```

---

## Part 3 — ML

**Data decisions:**
- Dropped `lead_id`, `crm_record_hash` (identifiers), `created_at` (not
  used in this baseline).
- Dropped `token_amount_received_pkr` — **leakage**. It's only populated
  after a lead converts (100% of converted leads have a value, ~99% of
  non-converted leads are 0), so it's effectively a copy of the label.
- Removed ~160 duplicate leads (same `crm_record_hash`, see Part 2).
- `bedrooms`: missing only for Commercial Shop / Plot listings, which
  structurally have no bedrooms — filled with 0, not the median.
- `city`: fixed inconsistent spelling/case (`ISB`, `Rwp`, `khi` → full
  lowercase city name).
- `area`: ~5% missing — filled with `"Unknown"` as its own category.
- `budget_pkr_lac`, `first_response_minutes`, `agent_experience_years`:
  a few percent missing, no structural reason — median-imputed.
- Kept `calls_made`, `total_call_seconds`, `whatsapp_replies`,
  `site_visits` — genuine engagement signals available during the sales
  process, not after the outcome.

**Model:** RandomForestClassifier, `class_weight="balanced"`, no tuning.

**Metric: ROC-AUC = 0.786.** Only ~7% of leads convert, so accuracy is
misleading (predicting "no" every time already scores ~93%). ROC-AUC
measures how well the model ranks converters above non-converters —
which is what actually matters for deciding which leads to call first.

**Run:**
```
cd part3_ML_Task
pip install pandas scikit-learn joblib
python train.py
```
This prints the metric and saves `lead_model.pkl`. A copy is kept in the
`docs/` root too, since that's where `streamlit_app.py` loads it from.

---

## Part 4 — Web

`streamlit_app.py` in `docs/` — one page, two tabs:
- **Document Assistant** — Part 1's Q&A with sources.
- **Lead Scoring** — bonus. Enter a lead's details, get a conversion
  likelihood % from the Part 3 model (`lead_model.pkl`).

**Run, from `docs/`:**
```
pip install streamlit
streamlit run streamlit_app.py
```

---

## Known issues / notes

- On some networks, IPv6 routes to Google's API are broken/blackholed,
  which makes the Python client hang far longer than a browser or `curl`
  would (curl falls back to IPv4 automatically; Python's http stack
  doesn't). `rag.py` forces IPv4-only DNS resolution to work around this.
- `gemini-2.5-flash`'s extended "thinking" is disabled
  (`thinking_budget=0`) to keep response latency reasonable.
- The Lead Scoring tab expects `lead_model.pkl` to exist in `docs/` — if
  missing, run `part3_ML_Task/train.py` and copy the file over.
