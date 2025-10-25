"""Get cleaned recipes from raw data"""
import pandas as pd
import json
import ast

DATA_PATH = "/Users/erlisalokaj/Desktop/SmartMeal/data/recipes_raw.csv"
OUTPUT_PATH = "/Users/erlisalokaj/Desktop/SmartMeal/data/recipes_clean.json"

def clean_list(text):
    try:
        return ast.literal_eval(text)
    except:
        return []

recipes_clean = []

chunksize = 5000
target_count = 300

for chunk in pd.read_csv(DATA_PATH, chunksize=chunksize):
    for _, row in chunk.iterrows():
        if len(recipes_clean) >= target_count:
            break

        if pd.isna(row["ingredients"]) or pd.isna(row["directions"]):
            continue

        ingredients = clean_list(row["ingredients"])
        steps = clean_list(row["directions"])

        if len(ingredients) < 2 or len(steps) < 2:
            continue

        recipe = {
            "name": row["title"],
            "ingredients": ingredients,
            "steps": steps,
            "source": row["link"]
        }
        recipes_clean.append(recipe)

    if len(recipes_clean) >= target_count:
        break

with open(OUTPUT_PATH, "w") as f:
    json.dump(recipes_clean, f, indent=2)

print(f"Cleaned {len(recipes_clean)} recipes")
print(f"Saved to {OUTPUT_PATH}")
