"""User Service"""
import logging
from adapters.sql_adapter import (
    init_postgres, upsert_user, get_user, list_users, set_pantry, get_pantry
)

log = logging.getLogger("smartmeal.users")

def ensure_bootstrap_user():
    init_postgres()
    init_postgres()
    log.info("db_initialized")

def create_or_update_user(name: str, goal: str):
    upsert_user(name, goal)
    log.info("user_upserted name=%s goal=%s", name, goal)
    return get_user(name)

def set_user_pantry(name: str, items: list[str]):
    set_pantry(name, items)
    log.info("pantry_set name=%s items=%d sample=%s", name, len(items), items[:5])
    return get_pantry(name)

def get_user_info(name: str):
    u = get_user(name)
    log.info("user_fetched name=%s found=%s", name, bool(u))
    return u

def get_all_users():
    users = list_users()
    log.info("users_listed count=%d", len(users))
    return users

def get_user_pantry(name: str):
    p = get_pantry(name)
    log.info("user_pantry name=%s items=%d", name, len(p))
    return p

__all__ = [
    "ensure_bootstrap_user",
    "get_user_info",
    "create_or_update_user",
    "get_all_users",
    "set_user_pantry",
    "get_user_pantry",
]
