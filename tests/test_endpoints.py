"""
Test for basic API health check.

This test ensures the FastAPI application is running and responding.
All other tests have been organized into dedicated test files:
- test_users.py: User and profile management (Use Cases 1 & 2)
- test_pantry.py: Pantry management (Use Case 5)
- test_waste.py: Waste tracking (Use Case 9)
- test_recommendations.py: Recipe recommendations (Use Case 7)
- test_shopping_list.py: Shopping list generation (Use Case 6)
"""

from test_fixtures import client


def test_health_check():
    """
    Test the health check endpoint.

    Verifies:
    1. GET /health-check returns 200 OK
    2. Response includes service name

    This is a basic smoke test to ensure the API is running.
    """
    r = client.get("/health-check")
    assert r.status_code == 200
    assert r.json()["service"] == "SmartMeal"
