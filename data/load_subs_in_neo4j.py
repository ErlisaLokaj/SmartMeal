import csv
from neo4j import GraphDatabase
from core.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

CSV_PATH = "/Users/erlisalokaj/Desktop/SmartMeal/data/ingredient_subs_FINAL.csv"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def ensure_constraint(tx):
    tx.run("""
    CREATE CONSTRAINT ingredient_name_unique IF NOT EXISTS
    FOR (i:Ingredient) REQUIRE i.name IS UNIQUE
    """)

def load_batch(tx, rows):
    tx.run("""
    UNWIND $rows AS row
    WITH toLower(row.ingredient) AS ing, toLower(row.substitute) AS sub
    WHERE ing <> '' AND sub <> ''
    MERGE (i:Ingredient {name: ing})
    MERGE (s:Ingredient {name: sub})
    MERGE (i)-[:SUBSTITUTE_FOR]->(s)
    """, rows=rows)

if __name__ == "__main__":
    with driver.session() as session:
        session.execute_write(ensure_constraint)

        batch_size = 1000
        batch = []
        count = 0

        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                batch.append(row)
                if len(batch) >= batch_size:
                    session.execute_write(load_batch, batch)
                    count += len(batch)
                    batch = []
            if batch:
                session.execute_write(load_batch, batch)
                count += len(batch)

    print(f"Loaded {count} substitution edges into Neo4j successfully ✅")
    driver.close()
