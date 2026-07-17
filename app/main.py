from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from app.config import settings
from app.api.v1.router import router as api_router
from app.database.session import engine
from app.models.base import Base

# Create all tables in SQLite database on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CT-200 Document Intelligence & QA Test Generation System",
    description="Backend API for reading CT-200 manuals, tracking version changes, and generating QA test cases.",
    version="1.0.0",
    debug=settings.DEBUG
)

# Root endpoint redirects to docs
@app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/docs")

# Include the API router
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
