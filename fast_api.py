from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlmodel import Field, Session, SQLModel, create_engine

# ====================== DATABASE CONFIG ======================
sqlite_url = "sqlite:///todo_data.db"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

def get_session():
    with Session(engine) as session:
        yield session

@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    print("✅ Database initialized successfully.")
    yield

# ====================== FASTAPI APP ======================
app = FastAPI(
    title="Todo API",
    description="Simple Todo Application built with FastAPI and SQLModel",
    version="0.1.0",
    lifespan=lifespan
)

@app.get("/")
def root():
    return {
        "message": "Todo API is running.",
        "docs": "/docs"
    }

print("🚀 Todo API started successfully!")
