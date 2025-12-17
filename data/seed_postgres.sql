-- -----------------------------
-- 1) Users
-- -----------------------------
INSERT INTO app_user (user_id, email, full_name, created_at, updated_at)
VALUES
    ('11111111-1111-1111-1111-111111111111', 'demo@smartmeal.io',  'Demo User',    NOW(), NOW()),
    ('22222222-2222-2222-2222-222222222222', 'demo2@smartmeal.io', 'Demo User 2',  NOW(), NOW())
ON CONFLICT (user_id) DO NOTHING;

-- -----------------------------
-- 2) Ingredients
-- -----------------------------
-- Mark chicken as allergen to test allergy filtering/recommendations
INSERT INTO ingredient (ingredient_id, name, category, is_allergen, created_at, updated_at)
VALUES
    ('87bfc225-7ba8-45db-96c9-7fee29ed6a28', 'whole chicken', 'protein', true,  NOW(), NOW()),
    ('737da0ee-985b-4448-b0d0-de61ae86b8f3', 'butter or margarine', 'dairy', false, NOW(), NOW()),
    ('278fb1e5-01f1-4b63-880a-56a12e37c0bc', 'milk', 'dairy', false, NOW(), NOW()),
    ('049ae1c1-dba4-4a75-a67a-4c9cc40b633b', 'cream of mushroom soup', 'canned', false, NOW(), NOW()),
    ('68e4332b-a14c-4207-b4d9-d81c32625e44', 'chicken gravy', 'canned', false, NOW(), NOW()),
    ('d38339f0-d5c8-406c-b0ae-6e15bf30a3b4', 'stuffing mix', 'grains', false, NOW(), NOW()),
    ('9f738f6a-d48f-41c8-a5fb-cf28d7f6ece1', 'shredded cheese', 'dairy', false, NOW(), NOW()),
    ('1838beb3-5f4d-4572-80e5-1278038e4699', 'brown sugar', 'baking', false, NOW(), NOW()),
    ('c8c37aa6-d1c4-404d-8378-bbb3843cfb42', 'vanilla', 'baking', false, NOW(), NOW()),
    ('88a7634a-6474-4b36-946e-fb9ed96ecbe6', 'broken nuts (pecans)', 'nuts', true, NOW(), NOW())
ON CONFLICT (ingredient_id) DO NOTHING;

-- -----------------------------
-- 3) Allergy (Demo user allergic to chicken)
-- -----------------------------

INSERT INTO user_allergy (user_id, ingredient_id)
VALUES
    ( '11111111-1111-1111-1111-111111111111', '87bfc225-7ba8-45db-96c9-7fee29ed6a28');

-- -----------------------------
-- 4) Dietary profile
-- -----------------------------
INSERT INTO dietary_profile (
    user_id,
    goal,
    activity,
    kcal_target,
    protein_target_g,
    carb_target_g,
    fat_target_g,
    cuisine_likes,
    cuisine_dislikes,
    updated_at
)
VALUES
    (
        '11111111-1111-1111-1111-111111111111',
        'WEIGHT_LOSS',
        'ACTIVE',
        1800,
        160,
        150,
        60,
        ARRAY['Japanese','Italian'],
        ARRAY['Indian'],
        NOW()
    ),
    (
        '22222222-2222-2222-2222-222222222222',
        'MUSCLE_GAIN',
        'MODERATE',
        2200,
        150,
        200,
        70,
        ARRAY['Mexican'],
        ARRAY[]::text[],
        NOW()
    )
ON CONFLICT (user_id) DO UPDATE SET
                                    goal = EXCLUDED.goal,
                                    activity = EXCLUDED.activity,
                                    kcal_target = EXCLUDED.kcal_target,
                                    protein_target_g = EXCLUDED.protein_target_g,
                                    carb_target_g = EXCLUDED.carb_target_g,
                                    fat_target_g = EXCLUDED.fat_target_g,
                                    cuisine_likes = EXCLUDED.cuisine_likes,
                                    cuisine_dislikes = EXCLUDED.cuisine_dislikes,
                                    updated_at = NOW();

-- -----------------------------
-- 5) User preferences
-- -----------------------------
INSERT INTO user_preference (user_id, tag, strength)
VALUES
    ('11111111-1111-1111-1111-111111111111', 'quick',      'LIKE'),
    ('11111111-1111-1111-1111-111111111111', 'vegetarian', 'LOVE'),
    ('11111111-1111-1111-1111-111111111111', 'spicy',      'AVOID')
ON CONFLICT DO NOTHING;

-- -----------------------------
-- 6) Pantry items
-- -----------------------------
INSERT INTO pantry_item (pantry_item_id, user_id, ingredient_id, quantity, unit, best_before, source, created_at, updated_at)
VALUES
    ('11111111-aaaa-aaaa-aaaa-111111111111', '11111111-1111-1111-1111-111111111111', '87bfc225-7ba8-45db-96c9-7fee29ed6a28', 1,    'unit', CURRENT_DATE + 2,  'seed', NOW(), NOW()),
    ('22222222-aaaa-aaaa-aaaa-222222222222', '11111111-1111-1111-1111-111111111111', '278fb1e5-01f1-4b63-880a-56a12e37c0bc', 1000, 'ml',   CURRENT_DATE + 10, 'seed', NOW(), NOW()),
    ('33333333-aaaa-aaaa-aaaa-333333333333', '11111111-1111-1111-1111-111111111111', '737da0ee-985b-4448-b0d0-de61ae86b8f3', 200,  'g',    CURRENT_DATE + 30, 'seed', NOW(), NOW())
ON CONFLICT (pantry_item_id) DO NOTHING;





