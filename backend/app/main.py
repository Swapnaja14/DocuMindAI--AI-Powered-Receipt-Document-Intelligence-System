import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, documents, search, users
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
app.include_router(search.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "Welcome to DocuMind AI Backend API"}


@app.get("/health")
def health_check():
    faiss_info = {"loaded": False, "total_vectors": 0, "mapped_chunks": 0}
    try:
        service = FAISSService()
        faiss_info = service.status()
    except Exception as err:
        faiss_info["error"] = str(err)

    return {
        "status": "healthy",
        "faiss": faiss_info,
    }

