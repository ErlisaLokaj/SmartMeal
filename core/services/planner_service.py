def generate_plan(user, recipes):
    plan = {
        "user": user["name"],
        "goal": user["goal"],
        "recipes": recipes["recipes"],
        "substitutes": recipes["alternatives"]
    }
    return plan
