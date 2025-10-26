"""Adapter for Neo4j graph database."""
from neo4j import GraphDatabase
from core.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
import logging
log = logging.getLogger("smartmeal.neo4j")


_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def get_substitutes(ingredient: str, limit: int = 5) -> list[str]:
    cypher = """
    MATCH (a:Ingredient {name:$name})-[:SUBSTITUTE_FOR]->(b:Ingredient)
    RETURN b.name AS sub
    LIMIT $limit
    """
    with _driver.session() as s:
        res = s.run(cypher, name=ingredient.lower(), limit=limit)
        subs = [r["sub"] for r in res]
        log.info("substitutes ingredient=%s count=%d", ingredient, len(subs))
        return subs

def close():
    _driver.close()
