import os
from dotenv import load_dotenv

load_dotenv()

POSTGRES_DB_URL = os.getenv(
    "POSTGRES_DB_URL", "postgresql+psycopg2://user@localhost:5432/smartmeal"
)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
