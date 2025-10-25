"""PostgreSQL adapter"""
from sqlalchemy import create_engine, text
from core.config import POSTGRES_DB_URL

engine = create_engine(POSTGRES_DB_URL, echo=False, future=True)

DDL = """
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  name VARCHAR(50) UNIQUE,
  goal VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS pantry (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  item TEXT
);

CREATE TABLE IF NOT EXISTS meal_plan (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  title TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);
"""

def init_postgres():
    with engine.begin() as conn:
        # multiple statements ok under begin()
        for stmt in DDL.strip().split(";\n\n"):
            if stmt.strip():
                conn.execute(text(stmt))

def upsert_user(name: str, goal: str):
    with engine.begin() as conn:
        conn.execute(text("""
          INSERT INTO users (name, goal)
          VALUES (:name, :goal)
          ON CONFLICT (name) DO UPDATE SET goal = EXCLUDED.goal
        """), {"name": name, "goal": goal})

def get_user(name: str):
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id, name, goal FROM users WHERE name = :name"
        ), {"name": name}).mappings().first()
        return dict(row) if row else None

def list_users():
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, name, goal FROM users ORDER BY id")).mappings().all()
        return [dict(r) for r in rows]

def set_pantry(name: str, items: list[str]):
    with engine.begin() as conn:
        uid = conn.execute(text("SELECT id FROM users WHERE name=:n"), {"n": name}).scalar()
        if uid is None:
            raise ValueError("User not found")
        conn.execute(text("DELETE FROM pantry WHERE user_id=:u"), {"u": uid})
        for it in items:
            conn.execute(text("INSERT INTO pantry (user_id, item) VALUES (:u, :it)"),
                         {"u": uid, "it": it})

def get_pantry(name: str) -> list[str]:
    with engine.connect() as conn:
        uid = conn.execute(text("SELECT id FROM users WHERE name=:n"), {"n": name}).scalar()
        if uid is None:
            return []
        rows = conn.execute(text("SELECT item FROM pantry WHERE user_id=:u"), {"u": uid}).all()
        return [r[0] for r in rows]
