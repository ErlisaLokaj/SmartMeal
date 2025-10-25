"""Adapter for Neo4j graph database."""
from neo4j import GraphDatabase
from core.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def get_substitutes(ingredient: str, limit: int = 5) -> list[str]:
    """
    Returns substitute ingredient names for a given ingredient.
    Expects a graph with (:Ingredient {name})-[:SUBSTITUTE_FOR]->(:Ingredient).
    """
    cypher = """
    MATCH (a:Ingredient {name:$name})-[:SUBSTITUTE_FOR]->(b:Ingredient)
    RETURN b.name AS sub
    LIMIT $limit
    """
    with _driver.session() as s:
        res = s.run(cypher, name=ingredient.lower(), limit=limit)
        return [r["sub"] for r in res]

def close():
    _driver.close()
