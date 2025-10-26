"""API routes"""
import logging
from http.client import HTTPException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
from adapters.sql_adapter import init_postgres
from fastapi import FastAPI, Query, Body
from adapters.sql_adapter import engine
from adapters.graph_adapter import close as close_neo4j


from adapters.graph_adapter import get_substitutes
from core.services.user_service import (
    ensure_bootstrap_user, get_user_info, create_or_update_user,
    get_all_users, set_user_pantry, get_user_pantry
)
from core.services.recipe_service import find_recipes_by_ingredient, find_recipes_by_name
from core.services.planner_service import generate_plan_for_ingredient
from api.schemas import RecipeSearchResponse, Plan

app = FastAPI(title="SmartMeal API", version="1.0.0",
              description="Personalized meal planning with PostgreSQL + MongoDB + Neo4j")

@app.on_event("startup")
def bootstrap():
    init_postgres()

@app.on_event("shutdown")
def shutdown_event():
    try:
        engine.dispose()
    except Exception:
        pass
    try:
        close_neo4j()
    except Exception:
        pass


@app.get("/health")
def health():
    return {"status": "ok"}

# ---------- Users ----------
@app.get("/users")
def users():
    return get_all_users()

@app.get("/users/{name}")
def user(name: str):
    return get_user_info(name)

@app.post("/users")
def upsert_user(name: str = Body(...), goal: str = Body(...)):
    return create_or_update_user(name, goal)

@app.put("/users/{name}/pantry")
def put_pantry(name: str, items: list[str] = Body(..., embed=True)):
    return {"pantry": set_user_pantry(name, items)}

@app.get("/users/{name}/pantry")
def get_pantry_api(name: str):
    return {"pantry": get_user_pantry(name)}

# ---------- Recipes ----------
@app.get("/recipes/search", response_model=RecipeSearchResponse)
def recipes_search(ingredient: str = Query(None), name: str = Query(None),
                   page: int = 1, size: int = 10):
    if ingredient:
        return find_recipes_by_ingredient(ingredient, page=page, size=size)
    if name:
        return find_recipes_by_name(name, page=page, size=size)
    return {"data": [], "meta": {"page": 1, "size": 10, "total": 0, "pages": 0}}

@app.get("/recipes/{ingredient}", response_model=RecipeSearchResponse)
def recipes_by_ingredient_simple(
    ingredient: str,
    limit: int = Query(10, ge=1, le=50, description="Max results to return (default 10, max 50)"),
):
    reserved = {"name", "search"}
    if ingredient.lower() in reserved:
        raise HTTPException(
            status_code=400,
            detail=f"'{ingredient}' is reserved. Use /recipes/name/{{name}} or /recipes/search?ingredient={{ingredient}}."
        )

    res = find_recipes_by_ingredient(ingredient, page=1, size=limit)
    res["meta"].update({"page": 1, "size": limit, "pages": 1, "total": len(res["data"])})
    return res

@app.get("/recipes/{name}", response_model=RecipeSearchResponse)
def recipes_by_name_simple(
    name: str,
    limit: int = Query(10, ge=1, le=50, description="Max results to return (default 10, max 50)"),
):
    res = find_recipes_by_name(name, page=1, size=limit)
    res["meta"].update({
        "page": 1,
        "size": limit,
        "pages": 1,
        "total": len(res["data"]),
    })
    return res

# ---------- Substitutions ----------
@app.get("/substitute/{ingredient}")
def substitute_simple(
    ingredient: str,
    limit: int = Query(10, ge=1, le=50, description="Max results (default 10, max 50)"),
):
    subs = get_substitutes(ingredient, limit=limit)
    return {"ingredient": ingredient, "substitutes": subs}

# ---------- Meal Plan ----------
@app.get("/plan", response_model=Plan)
def plan(user: str = Query(..., description="User name"),
         ingredient: str = Query(..., description="Main ingredient"),
         top_n: int = 10):
    return generate_plan_for_ingredient(user, ingredient, top_n=top_n)


@app.get("/plan/{user}/{ingredient}", response_model=Plan)
def plan_simple(
    user: str,
    ingredient: str,
    top: int = Query(5, ge=1, le=100, description="How many recipes to include (default 5, max 100)"),
):
    """
    Generate a personalized meal plan centered on `ingredient` for `user`.

    - Pulls user+pantry from PostgreSQL
    - Finds & ranks recipes from MongoDB by user goal
    - Gets substitutes from Neo4j
    - Builds shopping_list {need, have} vs pantry
    """
    return generate_plan_for_ingredient(user, ingredient, top_n=top)

