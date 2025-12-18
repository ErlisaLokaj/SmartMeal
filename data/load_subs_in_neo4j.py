"""Load substitution pairs into Neo4j.
"""

import json
import os
from pathlib import Path
#from app.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "neo4jpassword"

try:
    from neo4j import GraphDatabase
except Exception as e:
    raise RuntimeError(
        "neo4j driver not available. Install with `pip install neo4j` to run this script"
    ) from e


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "substitution_pairs.json"
if not DATA_PATH.exists():
    DATA_PATH = Path(os.getenv("SUBS_JSON_PATH", str(DATA_PATH)))

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def ensure_constraints(tx):
    # create proc_id uniqueness and name uniqueness
    tx.run(
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Ingredient) REQUIRE n.proc_id IS UNIQUE"
    )
    tx.run(
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Ingredient) REQUIRE n.name IS UNIQUE"
    )


def load_batch_by_proc(tx, rows):
    tx.run(
        """
        UNWIND $rows AS row
        MERGE (i:Ingredient {proc_id: row.ing_proc_id})
        ON CREATE SET i.name = row.ingredient_name
        MERGE (s:Ingredient {proc_id: row.sub_proc_id})
        ON CREATE SET s.name = row.sub_name
        MERGE (i)-[:SUBSTITUTE_FOR]->(s)
        """,
        rows=rows,
    )


def load_batch_by_name(tx, rows):
    tx.run(
        """
        UNWIND $rows AS row
        MERGE (i:Ingredient {name: row.ingredient_name})
        MERGE (s:Ingredient {name: row.sub_name})
        MERGE (i)-[:SUBSTITUTE_FOR]->(s)
        """,
        rows=rows,
    )


def normalize_str(s: str):
    return s.strip().lower() if s and isinstance(s, str) else None


def rows_from_json_iter(iterable):
    for rec in iterable:
        ing_name = normalize_str(rec.get("ingredient"))
        sub_name = normalize_str(rec.get("substitution"))
        ing_proc = rec.get("ingredient_processed_id")
        sub_proc = rec.get("substitution_processed_id")
        # prefer processed ids but allow names when ids missing
        yield {
            "ingredient_name": ing_name,
            "sub_name": sub_name,
            "ing_proc_id": ing_proc,
            "sub_proc_id": sub_proc,
        }


def main(batch_size: int = 2000):
    with driver.session() as session:
        session.execute_write(ensure_constraints)

        # Load JSON file
        count = 0
        proc_batch = []
        name_batch = []

        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            for rec in rows_from_json_iter(data):
                ing_proc = rec["ing_proc_id"]
                sub_proc = rec["sub_proc_id"]
                # If both processed ids present use proc_id based merge
                if ing_proc and sub_proc:
                    proc_batch.append(
                        {
                            "ingredient_name": rec["ingredient_name"],
                            "sub_name": rec["sub_name"],
                            "ing_proc_id": rec["ing_proc_id"],
                            "sub_proc_id": rec["sub_proc_id"],
                        }
                    )
                else:
                    # fallback to name-based merge if names are present
                    if rec["ingredient_name"] and rec["sub_name"]:
                        name_batch.append(
                            {
                                "ingredient_name": rec["ingredient_name"],
                                "sub_name": rec["sub_name"],
                            }
                        )

                if len(proc_batch) >= batch_size:
                    session.execute_write(load_batch_by_proc, proc_batch)
                    count += len(proc_batch)
                    proc_batch = []

                if len(name_batch) >= batch_size:
                    session.execute_write(load_batch_by_name, name_batch)
                    count += len(name_batch)
                    name_batch = []

        # flush remaining
        if proc_batch:
            session.execute_write(load_batch_by_proc, proc_batch)
            count += len(proc_batch)
        if name_batch:
            session.execute_write(load_batch_by_name, name_batch)
            count += len(name_batch)

    driver.close()
    print(f"Loaded {count} substitution edges into Neo4j successfully")


if __name__ == "__main__":
    main()
