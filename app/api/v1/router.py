from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database.session import get_db

router = APIRouter(prefix="/api/v1")

@router.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """
    Perform a health check verification.
    Validates that the database connection is functional.
    """
    try:
        # Execute simple query to test DB connection
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "ok",
        "database": db_status
    }
