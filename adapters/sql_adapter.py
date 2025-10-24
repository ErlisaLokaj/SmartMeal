import sqlite3

def setup_sql_demo():
    conn = sqlite3.connect("smartmeal.db")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, goal TEXT)")
    cur.execute("DELETE FROM users")
    cur.execute("INSERT INTO users (name, goal) VALUES (?, ?)", ("Anna", "High Protein Meals"))
    conn.commit()
    conn.close()

def get_user(name: str):
    conn = sqlite3.connect("smartmeal.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE name=?", (name,))
    result = cur.fetchone()
    conn.close()
    if result:
        return {"id": result[0], "name": result[1], "goal": result[2]}
    return None
