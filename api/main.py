"""
FastAPI Application Entry Point — CloudFinOps AI Infrastructure Cost Audit API.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from api.routes.audit import router as audit_router
from qdrant.vector_store import get_vector_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure Qdrant collection is ready
    print("[API] Starting CloudFinOps API...")
    try:
        vs = get_vector_store()
        vs.init_collection(recreate=False)
        print("[API] Qdrant collection verified.")
    except Exception as e:
        print(f"[API] Warning: Could not verify Qdrant at startup: {e}")
    yield
    print("[API] Shutting down CloudFinOps API...")


app = FastAPI(
    title="CloudFinOps — Cloud Infrastructure Cost Audit API",
    description="Beginner-friendly AI Engineering solution for AWS cloud cost auditing.",
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

app.include_router(audit_router, tags=["FinOps Audit"])


@app.get("/")
def root():
    return {
        "service": "CloudFinOps API",
        "status": "online",
        "endpoints": {
            "audit": "POST /audit",
            "docs": "/docs",
        },
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
