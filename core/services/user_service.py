from adapters.sql_adapter import get_user, setup_sql_demo

def get_user_info(name: str):
    setup_sql_demo()
    user = get_user(name)
    return user or {"name": name, "goal": "Balanced Diet"}
