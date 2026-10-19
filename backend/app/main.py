import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, documents, expenses, health, rag, search, users
from app.core.config import settings
from app.core.database import create_indexes
from app.services.faiss_service import FAISSService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database indexes
    try:
        create_indexes()
    except Exception as e:
        logger.warning("Database initialization note: %s", e)

    # Startup: Load and validate persistent FAISS vector index
    try:
        faiss_service = FAISSService()
        status = faiss_service.status()
        logger.info(
            "FAISS index loaded at startup: %d vectors, %d mapped chunks (status: %s)",
            status["total_vectors"],
            status["mapped_chunks"],
            "loaded" if status["loaded"] else "uninitialized",
        )
    except Exception as e:
        logger.error("FAISS index startup load failure: %s", e)

    yield
    # Shutdown logic if needed


app = FastAPI(
    title="DocuMind AI",
    description="AI-Powered Receipt & Document Intelligence System",
    version="1.0.0",
    lifespan=lifespan,
    debug=settings.debug,
)

# Configure CORS
allowed_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if not allowed_origins:
    allowed_origins = ["http://localhost:5173", "http://localhost:3000"]
if settings.is_production and "*" in allowed_origins:
    logger.warning("CORS wildcard '*' is prohibited in production with credentials. Reverting to localhost origins.")
    allowed_origins = ["http://localhost:5173", "http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Health & Operational Monitoring Routers
app.include_router(health.router)
app.include_router(health.router, prefix="/api/v1")

# Register API Routers
app.include_router(auth.router, prefix="/api")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api")
app.include_router(users.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api")
app.include_router(search.router, prefix="/api/v1")
app.include_router(rag.router, prefix="/api")
app.include_router(rag.router, prefix="/api/v1")
app.include_router(expenses.router, prefix="/api")
app.include_router(expenses.router, prefix="/api/v1")


@app.get("/")
def root():
    return {"message": "Welcome to DocuMind AI Backend API"}

