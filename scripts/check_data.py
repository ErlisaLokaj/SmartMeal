import json

with open('/Users/erlisalokaj/Desktop/SmartMeal/data/substitution_pairs_nested.json') as f:
    data = json.load(f)

proc_ids = []
null_count = 0

for item in data:
    pid = item.get('proc_id')
    if pid is None:
        null_count += 1
    else:
        proc_ids.append(pid)

    for sub in item.get('substitutes', []):
        sub_pid = sub.get('proc_id')
        if sub_pid is None:
            null_count += 1
        else:
            proc_ids.append(sub_pid)

total = len(proc_ids) + null_count
unique = len(set(proc_ids))
duplicates = len(proc_ids) - unique

print(f"Total proc_ids: {total}")
print(f"NULL proc_ids: {null_count}")
print(f"Unique proc_ids: {unique}")
print(f"Duplicate proc_ids: {duplicates}")

# Show first duplicate
from collections import Counter

counts = Counter(proc_ids)
for pid, count in counts.most_common(5):
    if count > 1:
        print(f"  '{pid}' appears {count} times")
