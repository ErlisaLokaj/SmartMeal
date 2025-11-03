#!/bin/sh
set -e

echo "================================================"
echo "SmartMeal Application Startup"
echo "================================================"

# Wait for PostgreSQL
echo "[1/3] Waiting for PostgreSQL..."
if [ -n "$POSTGRES_USER" ]; then
  until pg_isready -h db -U "$POSTGRES_USER"; do
    echo "  → Waiting for PostgreSQL to be ready..."
    sleep 1
  done
else
  until pg_isready -h db; do
    echo "  → Waiting for PostgreSQL to be ready..."
    sleep 1
  done
fi
echo "  ✓ PostgreSQL is ready!"

# Wait for MongoDB
echo "[2/3] Waiting for MongoDB..."
until python - <<'PY'
import os, sys
from pymongo import MongoClient
try:
    uri = os.environ.get('MONGO_URI', 'mongodb://mongo:27017')
    client = MongoClient(uri, serverSelectionTimeoutMS=2000)
    client.admin.command('ping')
    client.close()
    sys.exit(0)
except Exception as e:
    sys.exit(1)
PY
do
  echo "  → Waiting for MongoDB to be ready..."
  sleep 2
done
echo "  ✓ MongoDB is ready!"

# Wait for Neo4j
echo "[3/3] Waiting for Neo4j..."
until python - <<'PY'
import os, sys
from neo4j import GraphDatabase, basic_auth
try:
    uri = os.environ.get('NEO4J_URI', 'bolt://neo4j:7687')
    user = os.environ.get('NEO4J_USER', 'neo4j')
    pw = os.environ.get('NEO4J_PASSWORD', 'neo4j')
    drv = GraphDatabase.driver(uri, auth=basic_auth(user, pw))
    drv.verify_connectivity()
    drv.close()
    sys.exit(0)
except Exception as e:
    sys.exit(1)
PY
do
  echo "  → Waiting for Neo4j to be ready..."
  sleep 2
done
echo "  ✓ Neo4j is ready!"

# Initialize all databases (PostgreSQL tables, MongoDB collections, Neo4j constraints)
echo ""
echo "================================================"
echo "Database Initialization"
echo "================================================"
python /app/scripts/init_databases.py
if [ $? -ne 0 ]; then
  echo "  ✗ Database initialization failed!"
  exit 1
fi

echo ""
echo "================================================"
echo "Starting Application: $@"
echo "================================================"
exec "$@"

