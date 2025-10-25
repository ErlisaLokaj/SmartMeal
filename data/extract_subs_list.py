"""Generate a list of ingredient substitutions"""
import json
import pandas as pd
import os

DATA_IN = "/Users/erlisalokaj/Desktop/SmartMeal/data/substitution_pairs.json"
DATA_OUT = "/Users/erlisalokaj/Desktop/SmartMeal/data/ingredient_subs.csv"

print("Loading substitution_pairs.json ...")
with open(DATA_IN, "r", encoding="utf-8") as f:
    subs = json.load(f)

rows = []
for rec in subs:
    ing = rec.get("ingredient", "").strip().lower()
    sub = rec.get("substitution", "").strip().lower()
    if ing and sub and ing != sub:
        rows.append({"ingredient": ing, "substitute": sub})

df = pd.DataFrame(rows).drop_duplicates()
df.to_csv(DATA_OUT, index=False)
print(f"Saved {len(df)} substitution edges → {DATA_OUT}")
