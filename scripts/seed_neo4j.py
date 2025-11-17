#!/usr/bin/env python3
"""Idempotent Neo4j seeder script.

Usage examples:
  python scripts/seed_neo4j.py --file data/substitution_pairs.json --uri bolt://localhost:7687 --user neo4j --password neo4jpassword

Good practices implemented:
- Idempotent writes using MERGE and constraints
- Batching with UNWIND for efficient writes
- Streaming JSON support via ijson when available, fallback to json
- Configurable via CLI flags or env vars
- Clear exit codes and logging
"""
import argparse
import json
import logging
import os
import sys
from typing import Iterator, List, Dict
from neo4j import GraphDatabase, basic_auth
import ijson

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("neo4j-seed")


def stream_pairs(path: str) -> Iterator[Dict]:
    """Yield substitution pair objects from a JSON file. Supports streaming if ijson is installed."""
    logger.info("Using ijson for streaming JSON")
    with open(path, "rb") as fh:
        # Expecting top-level array of objects
        for item in ijson.items(fh, "item"):
            yield item



def chunked(iterator: Iterator, size: int) -> Iterator[List]:
    batch = []
    for item in iterator:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def ensure_constraints(tx):
    # Create constraints that make MERGE idempotent (Neo4j 4+ syntax)
    logger.info("Ensuring constraints")
   # tx.run(
     #   "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Ingredient) REQUIRE (i.proc_id) IS UNIQUE"
    #)
    tx.run(
        "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Ingredient) REQUIRE (i.id) IS UNIQUE"
    )
    tx.run(
        "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Ingredient) REQUIRE (i.name) IS UNIQUE"
    )


def write_batch(tx, batch: List[Dict]):
    # Each item expected to have: name, proc_id (optional), substitutes: list of dicts with name/proc_id
    # We build a parameterized UNWIND payload to MERGE nodes and relationships.
    pairs = []
    for item in batch:
        base = {"name": item.get("name"), "proc_id": item.get("proc_id"), "id": item.get("id")}
        for sub in item.get("substitutes", []) or []:
            pairs.append(
                {
                    "base_name": base["name"],
                    "base_proc": base.get("proc_id"),
                    "base_id": base.get("id"),
                    "sub_name": sub.get("name"),
                    "sub_proc": sub.get("proc_id"),
                    "sub_id": sub.get("id"),
                }
            )

    if not pairs:
        return

    # UNWIND pairs and MERGE Ingredient nodes by proc_id when present otherwise by name
    # Create or update nodes; set both proc_id and id when available and set shelf_life_days if present in pair
    query = """
    UNWIND $pairs AS p
    MERGE (b:Ingredient {name: p.base_name})
    SET b.proc_id = coalesce(b.proc_id, p.base_proc), b.id = coalesce(b.id, p.base_id)
    MERGE (s:Ingredient {name: p.sub_name})
    SET s.proc_id = coalesce(s.proc_id, p.sub_proc), s.id = coalesce(s.id, p.sub_id)
    MERGE (b)-[r:SUBSTITUTED_BY]->(s)
    RETURN count(r) as created
    """
    tx.run(query, pairs=pairs)


def seed(
    uri: str,
    user: str,
    password: str,
    file: str,
    batch_size: int = 1000,
    create_constraints: bool = True,
):
    logger.info("Connecting to Neo4j %s", uri)
    driver = GraphDatabase.driver(uri, auth=basic_auth(user, password))
    try:
        with driver.session() as session:
            session.execute_write(lambda tx: None)  # quick connectivity check
            if create_constraints:
                session.execute_write(lambda tx: ensure_constraints(tx))

            logger.info("Starting load from %s (batch_size=%s)", file, batch_size)
            it = stream_pairs(file)
            total = 0
            for batch in chunked(it, batch_size):

                def _write(tx):
                    write_batch(tx, batch)

                session.execute_write(_write)
                total += len(batch)
                logger.info("Wrote batch, total items processed: %d", total)

    finally:
        driver.close()


def main():
    p = argparse.ArgumentParser(
        description="Seed Neo4j with substitution pairs (idempotent)."
    )
    p.add_argument("--file", required=True, help="Path to substitution_pairs.json")
    p.add_argument(
        "--uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    )
    p.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    p.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD", "neo4j"))
    p.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of items per transaction batch",
    )
    p.add_argument(
        "--no-constraints",
        dest="constraints",
        action="store_false",
        help="Do not create constraints",
    )
    args = p.parse_args()

    if not os.path.exists(args.file):
        logger.error("Data file not found: %s", args.file)
        sys.exit(2)

    try:
        seed(
            args.uri,
            args.user,
            args.password,
            args.file,
            batch_size=args.batch_size,
            create_constraints=args.constraints,
        )
        logger.info("Seeding completed successfully")
    except Exception:
        logger.exception("Seeding failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
