CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  goal TEXT,
  pantry TEXT[]
);

INSERT INTO users (name, goal)
VALUES ('Anna', 'High Protein Meals')
ON CONFLICT (name) DO UPDATE SET goal = EXCLUDED.goal;
