# SmartMeal
SmartMeal is an intelligent meal planning system that integrates SQL, NoSQL, and Graph databases to create personalized weekly meal plans based on user preferences, available ingredients, and nutritional goals.

The system generates personalized meal plans based on:
 - User dietary goals
 - Ingredients already available in the pantry
 - Alternative ingredient recommendations  
 - Meal plans for user based on dietary goals and pantry

---

##  Quick Start

### Requirements
- Install requirements.txt
- Docker Desktop installed and running

### Run the full system
```bash
docker compose up -d --build
```

Access:
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs

---

## Import Sample Data

### MongoDB — Recipes
```bash
docker cp ./data/recipes_clean.json smartmeal-mongo-1:/tmp/recipes.json
docker exec smartmeal-mongo-1 mongoimport \
  --db smartmeal --collection recipes \
  --file /tmp/recipes.json --jsonArray
```

### Neo4j — Ingredient Substitutions
Start a local file server:
```bash
cd ./data && python3 -m http.server 8080
```

Then load data into Neo4j:
```bash
docker exec smartmeal-neo4j-1 cypher-shell -u neo4j -p smartmeal-neo4j \
"LOAD CSV WITH HEADERS FROM 'http://host.docker.internal:8080/ingredient_subs_FINAL.csv' AS row
 MERGE (a:Ingredient {name: toLower(row.ingredient)})
 MERGE (b:Ingredient {name: toLower(row.substitute)})
 MERGE (a)-[:SUBSTITUTE_FOR]->(b);"
```

---

## Example API Requests

| Description                       | Method & Path                                             |
|-----------------------------------|-----------------------------------------------------------|
| List users                        | `GET /users`                                              |
| Create user                       | `POST /users {"name":"Anna","goal":"High Protein Meals"}` |
| Update pantry                     | `PUT /users/Anna/pantry {"items":["rice"]}`               |
| Search recipes by ingredient name | `GET /recipes/chicken`                                    |
| Generate plan                     | `GET /plan/Anna/chicken`                                  |
| Ingredient substitutions          | `GET /substitute/chicken`                                 |

---

## Project Structure

```
api/          → FastAPI route handlers
core/         → Business logic services
adapters/     → PostgreSQL / MongoDB / Neo4j data access layers
data/         → Recipe + ingredient substitution source files
docker/       → Database initialization files
```

---


