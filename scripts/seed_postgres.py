import os
from sqlalchemy import create_engine, text

CURRENT_FILE = os.path.abspath(__file__)
SCRIPTS_DIR = os.path.dirname(CURRENT_FILE)
PROJECT_ROOT = os.path.dirname(SCRIPTS_DIR)
SEED_FILE = os.path.join(PROJECT_ROOT, "data", "seed_postgres.sql")


def get_engine():
    db_url = os.getenv("POSTGRES_DB_URL")
    if not db_url:
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "smartmeal")
        user = os.getenv("POSTGRES_USER", "postgres")
        pw = os.getenv("POSTGRES_PASSWORD", "postgres")
        db_url = f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}"

    return create_engine(db_url, future=True)


def run_sql_file(engine, path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Seed SQL file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()

    statements = [s.strip() for s in sql.split(";") if s.strip()]

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def main():
    enabled = os.getenv("POSTGRES_AUTO_SEED", "true").lower() in ("1", "true", "yes", "y")
    if not enabled:
        print("PostgreSQL seed is disabled (POSTGRES_AUTO_SEED=false)")
        return

    print("Seeding PostgreSQL...")
    engine = get_engine()
    run_sql_file(engine, SEED_FILE)
    print("✓ PostgreSQL seed done")


if __name__ == "__main__":
    main()
