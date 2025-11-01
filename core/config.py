import os
from dotenv import load_dotenv

load_dotenv()

POSTGRES_DB_URL = os.getenv(
    "POSTGRES_DB_URL", "postgresql+psycopg2://user@localhost:5432/smartmeal"
)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "smartmeal")