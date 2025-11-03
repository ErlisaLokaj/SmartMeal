"""Transform flat substitution data to nested format."""

import json
from collections import defaultdict
from pathlib import Path

input_file = Path("/Users/erlisalokaj/Desktop/SmartMeal/data/substitution_pairs.json")
output_file = Path("/Users/erlisalokaj/Desktop/SmartMeal/data/substitution_pairs_nested.json")

# Read flat data
with open(input_file) as f:
    flat_data = json.load(f)

# Group by ingredient
grouped = defaultdict(lambda: {"name": None, "proc_id": None, "substitutes": []})

for item in flat_data:
    ing_name = item["ingredient"]
    ing_id = item["ingredient_processed_id"]
    sub_name = item["substitution"]
    sub_id = item["substitution_processed_id"]

    # Set base ingredient info
    if grouped[ing_name]["name"] is None:
        grouped[ing_name]["name"] = ing_name
        grouped[ing_name]["proc_id"] = ing_id

    # Add substitute (if valid)
    if sub_name and sub_id:
        grouped[ing_name]["substitutes"].append({
            "name": sub_name,
            "proc_id": sub_id
        })

# Convert to list
nested_data = list(grouped.values())

# Write output
with open(output_file, 'w') as f:
    json.dump(nested_data, f, indent=2)

print(f"Transformed {len(flat_data)} pairs into {len(nested_data)} ingredients")
print(f"Saved to: {output_file}")
