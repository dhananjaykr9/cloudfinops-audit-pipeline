from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from api.routes.audit import router as audit_router
from qdrant.vector_store import get_vector_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        get_vector_store().init_collection(recreate=False)
    except Exception as e:
        print(f"Warning: Could not connect to Qdrant on startup: {e}")
    yield


app = FastAPI(
    title="Cloud Infrastructure Cost Audit API",
    description="AWS cloud cost auditing pipeline.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(audit_router, tags=["Cost Audit"])


@app.get("/")
def root():
    return {
        "service": "Cloud Infrastructure Cost Audit API",
        "status": "online",
        "endpoints": {
            "audit": "POST /audit",
            "docs": "/docs",
        },
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
