from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, documents, users
from app.core.database import create_indexes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Try to initialize database indexes
    try:
        create_indexes()
    except Exception as e:
        print(f"Database initialization note: {e}")
    yield
    # Shutdown logic if needed


app = FastAPI(
    title="DocuMind AI",
    description="AI-Powered Receipt & Document Intelligence System",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(documents.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "Welcome to DocuMind AI Backend API"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
