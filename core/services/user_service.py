"""User Service"""
from adapters.sql_adapter import init_postgres, upsert_user, get_user, list_users, set_pantry, get_pantry

def ensure_bootstrap_user():
    init_postgres()
    upsert_user("Anna", "High Protein Meals")

def get_user_info(name: str):
    init_postgres()
    return get_user(name)

def create_or_update_user(name: str, goal: str):
    init_postgres()
    upsert_user(name, goal)
    return get_user(name)

def set_user_pantry(name: str, items: list[str]):
    init_postgres()
    set_pantry(name, items)
    return get_pantry(name)

def get_user_pantry(name: str):
    init_postgres()
    return get_pantry(name)

def get_all_users():
    init_postgres()
    return list_users()
