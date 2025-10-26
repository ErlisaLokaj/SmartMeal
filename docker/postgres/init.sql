\c smartmeal;

CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  name VARCHAR(50) UNIQUE NOT NULL,
  goal VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS pantry (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  item TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meal_plan (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  ingredient TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS meal_plan_recipes (
  id SERIAL PRIMARY KEY,
  meal_plan_id INTEGER NOT NULL REFERENCES meal_plan(id) ON DELETE CASCADE,
  recipe_name TEXT NOT NULL,
  recipe_source TEXT,
  position INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_users_name ON users(name);
CREATE INDEX IF NOT EXISTS idx_pantry_user ON pantry(user_id);
CREATE INDEX IF NOT EXISTS idx_meal_plan_user ON meal_plan(user_id);
CREATE INDEX IF NOT EXISTS idx_meal_plan_recipes_plan ON meal_plan_recipes(meal_plan_id);