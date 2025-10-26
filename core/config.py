"""Application configuration"""
import os
from dotenv import load_dotenv
load_dotenv()

POSTGRES_DB_URL = os.getenv(
    "POSTGRES_DB_URL",
    "postgresql+psycopg2://smartmeal:smartmeal@localhost:5432/smartmeal"
)


MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "smartmeal-neo4j")
