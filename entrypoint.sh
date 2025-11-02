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

# Auto-seed Neo4j if enabled and no Ingredient nodes exist
if [ "${NEO4J_AUTO_SEED:-true}" = "true" ]; then
  echo ""
  echo "================================================"
  echo "Neo4j Auto-Seed Check"
  echo "================================================"
  python - <<'PY'
import os, sys, subprocess

from neo4j import GraphDatabase, basic_auth

uri = os.environ.get('NEO4J_URI', 'bolt://neo4j:7687')
user = os.environ.get('NEO4J_USER', 'neo4j')
pw = os.environ.get('NEO4J_PASSWORD', 'neo4j')

try:
    drv = GraphDatabase.driver(uri, auth=basic_auth(user, pw))
    with drv.session() as s:
        try:
            r = s.run('MATCH (n:Ingredient) RETURN count(n) AS cnt')
            cnt = r.single().get('cnt')
        except Exception:
            cnt = 0
    drv.close()
    
    if not cnt:
        print('  → No Ingredient nodes found - running seeder...')
        rc = subprocess.call([
            'python', 
            '/app/scripts/seed_neo4j.py', 
            '--file', '/app/data/substitution_pairs.json',
            '--uri', uri,
            '--user', user,
            '--password', pw
        ])
        if rc != 0:
            print(f'  ✗ Seeder failed with code {rc}')
            sys.exit(rc)
        else:
            print('  ✓ Neo4j seeding completed successfully!')
    else:
        print(f'  ✓ Found {cnt} Ingredient nodes - skipping seeding')
except Exception as e:
    print(f'  ✗ Error during Neo4j seed check: {e}')
    sys.exit(1)
PY
fi

echo ""
echo "================================================"
echo "Starting Application: $@"
echo "================================================"
exec "$@"

