"""
train.py — Part 3: baseline lead-scoring model.

Run:
    pip install pandas scikit-learn
    python train.py

============================================================
DATA DECISIONS
============================================================
DROPPED:
- lead_id, crm_record_hash: identifiers, not real features.
- created_at: raw timestamp, not useful for a quick baseline.
- token_amount_received_pkr: LEAKAGE. This column is only filled in
  AFTER a lead converts (it's the booking token) — 100% of converted
  leads have a value here, almost all non-converted leads have 0.
  Using it would let the model "see the answer" during training.

DEDUPLICATED:
- ~160 leads were entered twice under two different lead_ids (see
  Part 2). Kept one copy of each.

FIXED:
- bedrooms: missing only for Commercial Shop / Plot listings, because
  those property types don't have bedrooms. Filled with 0 (not a
  median — there's no "typical" bedroom count for a shop).
- city: inconsistent spelling ("Islamabad" / "ISLAMABAD" / "ISB").
  Lower-cased and abbreviations mapped to the full name.
- area: ~5% missing — filled with "Unknown" as its own category.
- budget_pkr_lac, first_response_minutes, agent_experience_years:
  a few percent missing, no clear reason — filled with the median.

KEPT:
- calls_made, total_call_seconds, whatsapp_replies, site_visits: real
  engagement signals a CRM would have during the sales process, so
  they're fair features for scoring a lead.
============================================================
"""

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
import joblib

# ---- 1. Load ----
df = pd.read_csv("leads.csv")

# ---- 2. Clean ----
df = df.drop_duplicates(subset="crm_record_hash", keep="first")

city_map = {"isb": "islamabad", "rwp": "rawalpindi", "khi": "karachi"}
df["city"] = df["city"].str.lower().str.strip().replace(city_map)

df["bedrooms"] = df["bedrooms"].fillna(0)
df["area"] = df["area"].fillna("Unknown")

df = df.drop(columns=["lead_id", "crm_record_hash", "created_at", "token_amount_received_pkr"])

# ---- 3. Split into inputs (X) and answer (y) ----
y = df["converted"]
X = df.drop(columns=["converted"])

numeric_cols = X.select_dtypes(include=["float64", "int64"]).columns.tolist()
categorical_cols = X.select_dtypes(include=["object", "string"]).columns.tolist()

# ---- 4. Train/test split ----
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)

# ---- 5. Build + train the model (no tuning) ----
preprocess = ColumnTransformer([
    ("num", SimpleImputer(strategy="median"), numeric_cols),
    ("cat", Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ]), categorical_cols),
])

model = Pipeline([
    ("preprocess", preprocess),
    ("clf", RandomForestClassifier(class_weight="balanced", random_state=42)),
])

model.fit(X_train, y_train)

# ---- 6. Score the test set and report one metric ----
y_proba = model.predict_proba(X_test)[:, 1]  # the "chance of converting" score, 0 to 1

auc = roc_auc_score(y_test, y_proba)

print(f"Class balance: {y.mean():.1%} converted / {(1 - y.mean()):.1%} not converted")
print(f"\nMETRIC: ROC-AUC = {auc:.3f}")
print("Chosen because only ~7% of leads convert — accuracy would be")
print("misleading here (predicting 'no' every time already scores ~93%).")
print("ROC-AUC measures how well the model ranks converters above")
print("non-converters, which is what actually matters for prioritising")
print("which leads the sales team should call first.")

# ---- 7. Save the trained model so the web app (Part 4) can reuse it
#         without retraining every time ----
joblib.dump(model, "lead_model.pkl")
print("\nSaved trained model to lead_model.pkl")