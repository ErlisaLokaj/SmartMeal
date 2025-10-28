from fastapi import FastAPI
import logging
import uvicorn
from api.profile_routes import router
from core.database.models import init_database

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

# Initialize database
init_database()

# Create FastAPI app
app = FastAPI(
    title="SmartMeal - Profile Management",
    version="1.0.0",
    description="Manage user profiles, dietary preferences, allergies"
)

# Include routers
app.include_router(router)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "profile-management"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)