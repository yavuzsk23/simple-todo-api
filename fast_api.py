from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlmodel import Field, Session, SQLModel, create_engine

# ====================== DATABASE CONFIGURATION ======================
# SQLite database connection settings
sqlite_url = "sqlite:///todo_data.db"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

# Helper function to get database session
def get_session():
    with Session(engine) as session:
        yield session

# Lifespan event - Runs when the application starts
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables on startup
    SQLModel.metadata.create_all(engine)
    print("✅ Database initialized successfully.")
    yield

# ====================== FASTAPI APPLICATION ======================
app = FastAPI(
    title="Todo API",
    description="Simple Todo Application built with FastAPI and SQLModel",
    version="0.1.0",
    lifespan=lifespan
)

@app.get("/")
def root():
    """Root endpoint - Returns basic API information"""
    return {
        "message": "Todo API is running.",
        "docs": "/docs",
        "status": "active"
    }

print("🚀 Todo API started successfully!")
