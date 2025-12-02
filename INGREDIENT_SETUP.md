# Ingredient Setup Workflow

This document explains how ingredients are synchronized across all three databases (MongoDB, PostgreSQL, and Neo4j) in the SmartMeal system.

## Problem Background

The SmartMeal system uses three databases for different purposes:
- **MongoDB**: Stores recipes with ingredient references (document store)
- **PostgreSQL**: Stores normalized ingredient master data (relational)
- **Neo4j**: Stores ingredient relationships and substitutions (graph)

All three databases need to be synchronized with a consistent set of ingredients and their UUIDs.

## Workflow During Application Startup

The `entrypoint.sh` script orchestrates the following steps:

### 1. Wait for Databases
- Wait for PostgreSQL to be ready
- Wait for MongoDB to be ready
- Wait for Neo4j to be ready

### 2. Initialize Database Schemas
```bash
python /app/scripts/init_databases.py
```
- Creates PostgreSQL tables (including `ingredients` table)
- Creates MongoDB collections and indexes
- Creates Neo4j constraints and indexes
- Auto-loads recipes from `data/recipes_structured.json` if MongoDB is empty

### 3. Create Ingredient Master Collection
```bash
python /app/scripts/create_ingredient_master.py
```
- Extracts all unique ingredients from the `recipes` collection
- Creates/updates the `ingredient_master` collection in MongoDB
- Maps ingredient names to their UUIDs (stored in recipe data)
- **Input**: Recipes in MongoDB with embedded ingredient data
- **Output**: `ingredient_master` collection with format:
  ```json
  {
    "_id": "ingredient name",
    "ingredient_id": "uuid-from-recipe"
  }
  ```

### 4. Migrate Ingredients to PostgreSQL
```bash
python /app/scripts/migrate_ingredients_from_mongo.py
```
- Reads ingredients from `ingredient_master` collection
- Inserts/updates ingredients in PostgreSQL `ingredients` table
- Links MongoDB documents back to PostgreSQL UUIDs
- **Input**: `ingredient_master` collection in MongoDB
- **Output**: Populated `ingredients` table in PostgreSQL

### 5. Sync Neo4j with Ingredient Master
```bash
python /app/scripts/sync_neo4j_with_ingridient.py
```
- Reads ingredients from `ingredient_master` collection
- Updates/creates Ingredient nodes in Neo4j with UUIDs
- Ensures Neo4j nodes have the `ingredient_id` property
- **Input**: `ingredient_master` collection in MongoDB
- **Output**: Ingredient nodes in Neo4j with `ingredient_id` property

### 6. Start the Application
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Scripts Overview

### `create_ingredient_master.py`
**Purpose**: Extract unique ingredients from recipes and create the master collection.

**When to run**: After recipes are loaded into MongoDB.

**Safe to run multiple times**: Yes, uses upsert operations.

### `migrate_ingredients_from_mongo.py`
**Purpose**: Migrate ingredients from MongoDB to PostgreSQL.

**When to run**: After `ingredient_master` collection is created.

**Safe to run multiple times**: Yes, checks for existing ingredients.

### `sync_neo4j_with_ingridient.py`
**Purpose**: Sync Neo4j Ingredient nodes with ingredient_master UUIDs.

**When to run**: After `ingredient_master` collection is created.

**Safe to run multiple times**: Yes, uses MERGE operations.

### `verify_ingredient_setup.py`
**Purpose**: Verify that ingredients are properly set up across all three databases.

**When to run**: After startup to validate the setup.

**Usage**:
```bash
python scripts/verify_ingredient_setup.py
```

## Data Flow

```
recipes_structured.json
    ↓
MongoDB recipes collection (with embedded ingredient UUIDs)
    ↓
MongoDB ingredient_master collection (extracted unique ingredients)
    ↓              ↓
    ↓              → Neo4j Ingredient nodes (with ingredient_id property)
    ↓
PostgreSQL ingredients table
```

## Troubleshooting

### Issue: "ingredient_master collection not found"
**Solution**: Ensure recipes are loaded into MongoDB first:
```bash
python scripts/load_recipes_to_mongo.py
python scripts/create_ingredient_master.py
```

### Issue: "No ingredients in PostgreSQL"
**Solution**: Run the complete workflow:
```bash
python scripts/create_ingredient_master.py
python scripts/migrate_ingredients_from_mongo.py
```

### Issue: "Neo4j nodes missing ingredient_id"
**Solution**: Run the sync script:
```bash
python scripts/sync_neo4j_with_ingridient.py
```

### Issue: "Verification fails"
**Solution**: Check the logs and re-run the failed step:
```bash
python scripts/verify_ingredient_setup.py
```

## Manual Setup

If you need to manually set up ingredients outside of Docker Compose:

```bash
# 1. Load recipes into MongoDB
python scripts/load_recipes_to_mongo.py

# 2. Create ingredient master collection
python scripts/create_ingredient_master.py

# 3. Migrate to PostgreSQL
python scripts/migrate_ingredients_from_mongo.py

# 4. Sync Neo4j
python scripts/sync_neo4j_with_ingridient.py

# 5. Verify setup
python scripts/verify_ingredient_setup.py
```

## Configuration

All scripts use environment variables from `docker-compose.yml`:

- `MONGO_URI`: MongoDB connection string (default: `mongodb://mongo:27017`)
- `MONGO_DB`: MongoDB database name (default: `smartmeal`)
- `NEO4J_URI`: Neo4j connection string (default: `bolt://neo4j:7687`)
- `NEO4J_USER`: Neo4j username (default: `neo4j`)
- `NEO4J_PASSWORD`: Neo4j password (default: `neo4jpassword`)
- `POSTGRES_DB_URL`: PostgreSQL connection string

## Notes

- All scripts are idempotent and safe to run multiple times
- The workflow happens automatically during Docker Compose startup
- Warnings are logged but don't stop the application from starting
- The system gracefully handles missing data and logs appropriate messages
