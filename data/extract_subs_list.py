import json
import pandas as pd
from tqdm import tqdm
import os

# Input files
SUBS_PATH = "/Users/erlisalokaj/Desktop/SmartMeal/data/ingredient_subs.csv"
EDAMAM_PATH = "/Users/erlisalokaj/Desktop/SmartMeal/data/edamam.json"

# Output
OUT_PATH = "/Users/erlisalokaj/Desktop/SmartMeal/data/ingredient_subs_filtered.csv"

# Load subs
subs = pd.read_csv(SUBS_PATH)

# Load Edamam metadata
with open(EDAMAM_PATH, "r") as f:
    edamam = json.load(f)

def get_category(name: str):
    # Find category label → simplified category mapping
    for k,v in edamam.items():
        n = v.get("ingredient_name","").lower()
        if n == name:
            return v.get("category","unknown").lower()
    return "unknown"

valid_rows = []
skipped = 0

print("Filtering based on ingredient category...")
for _, row in tqdm(subs.iterrows(), total=len(subs)):
    ing = row["ingredient"]
    sub = row["substitute"]

    cat_ing = get_category(ing)
    cat_sub = get_category(sub)

    # Only keep if categories match and are real foods
    if cat_ing != "unknown" and cat_ing == cat_sub:
        valid_rows.append({"ingredient": ing, "substitute": sub})
    else:
        skipped += 1

pd.DataFrame(valid_rows).to_csv(OUT_PATH, index=False)

print(f"\n Filtered substitutions: {len(valid_rows)} kept")
print(f"Skipped noisy entries: {skipped}")
print(f"Saved → {OUT_PATH}")
