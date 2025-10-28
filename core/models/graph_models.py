"""Neo4j models."""
from neomodel import (
    StructuredNode,
    StringProperty,
    RelationshipTo,
    RelationshipFrom,
    config
)
from core.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

config.DATABASE_URL = f"bolt://{NEO4J_USER}:{NEO4J_PASSWORD}@{NEO4J_URI.replace('bolt://', '')}"
config.AUTO_INSTALL_LABELS = True


class Ingredient(StructuredNode):
    """Ingredient node with substitute relationships."""
    name = StringProperty(unique_index=True, required=True)

    # Relationships
    substitutes = RelationshipTo('Ingredient', 'SUBSTITUTE_FOR')
    used_in = RelationshipFrom('Recipe', 'CONTAINS')

    def __repr__(self):
        return f"<Ingredient: {self.name}>"


class Recipe(StructuredNode):
    """Recipe node linked to ingredients."""
    name = StringProperty(unique_index=True, required=True)

    # Relationships
    contains = RelationshipTo('Ingredient', 'CONTAINS')

    def __repr__(self):
        return f"<Recipe: {self.name}>"