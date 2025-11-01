#!/bin/sh
set -e

echo "entrypoint: waiting for services"

# Wait for Postgres
if [ -n "$POSTGRES_USER" ]; then
  until pg_isready -h db -U "$POSTGRES_USER"; do
    echo "Waiting for db..."
    sleep 1
  done
else
  until pg_isready -h db; do
    echo "Waiting for db..."
    sleep 1
  done
fi

# Wait for Neo4j
echo "entrypoint: waiting for neo4j"
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
except Exception:
    sys.exit(1)
PY
do
  echo "Waiting for neo4j..."
  sleep 2
done

# Auto-seed if enabled and Neo4j has no Ingredient nodes
if [ "${NEO4J_AUTO_SEED:-true}" = "true" ]; then
  echo "entrypoint: checking whether to seed neo4j"
  python - <<'PY'
import os, sys, subprocess
from neo4j import GraphDatabase, basic_auth
uri = os.environ.get('NEO4J_URI', 'bolt://neo4j:7687')
user = os.environ.get('NEO4J_USER', 'neo4j')
pw = os.environ.get('NEO4J_PASSWORD', 'neo4j')
drv = GraphDatabase.driver(uri, auth=basic_auth(user, pw))
with drv.session() as s:
    try:
        r = s.run('MATCH (n:Ingredient) RETURN count(n) AS cnt')
        cnt = r.single().get('cnt')
    except Exception:
        cnt = 0
drv.close()
if not cnt:
    print('No Ingredient nodes found — running seeder')
    rc = subprocess.call(['python', '/app/scripts/seed_neo4j.py', '--file', '/app/data/substitution_pairs.json', '--uri', uri, '--user', user, '--password', pw])
    if rc != 0:
        print('Seeder failed with code', rc)
        sys.exit(rc)
else:
    print(f'Ingredient nodes present: {cnt}; skipping seeding')
PY
fi

echo "entrypoint: exec: $@"
exec "$@"
