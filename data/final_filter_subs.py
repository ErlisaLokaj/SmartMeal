import pandas as pd

IN = "/Users/erlisalokaj/Desktop/SmartMeal/data/ingredient_subs_filtered.csv"
OUT = "/Users/erlisalokaj/Desktop/SmartMeal/data/ingredient_subs_FINAL.csv"

BAD_WORDS = [
    "garlic", "onion", "green onion", "scallion", "shallot",
    "salt", "pepper", "seasoning", "spice", "herb", "stock",
    "broth", "cream", "paste", "sauce", "gravy",
    "cookie", "sugar", "sweet", "flour", "rice", "bread", "noodle",
    "powder", "crumb", "vinegar", "lemon", "lime", "ginger",
]

def is_bad(name):
    n = name.lower()
    return any(word in n for word in BAD_WORDS)

df = pd.read_csv(IN)

filtered = df[
    (~df["ingredient"].apply(is_bad)) &
    (~df["substitute"].apply(is_bad))
].drop_duplicates()

filtered.to_csv(OUT, index=False)
print(f"FINAL substitutions: {len(filtered)} kept → {OUT}")
