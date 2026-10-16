"""
Main FastAPI Application

Entry point for the AV Ethics Simulator backend.
Configures FastAPI app, CORS, routes, and database initialization.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import init_db
from routers import scenarios


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Runs initialization code on startup and cleanup on shutdown.
    """
    # Startup: Initialize database
    print("Initializing database...")
    init_db()
    print("Database initialized successfully")

    yield

    # Shutdown: Cleanup if needed
    print("Shutting down...")


# Create FastAPI application instance
app = FastAPI(
    title="AV Ethics Simulator API",
    description="API for configuring and simulating autonomous vehicle ethical dilemmas",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS (Cross-Origin Resource Sharing)
# Allows frontend to make requests from different origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "http://localhost:5173",  # Vite dev server
        "http://frontend:3000",   # Docker container
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Include routers
app.include_router(scenarios.router)


# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint - API health check.

    Returns basic API information.
    """
    return {
        "message": "AV Ethics Simulator API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "characters": "/api/characters",
            "scenarios": "/api/scenarios",
            "statistics": "/api/statistics"
        }
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.

    Returns:
        Status information
    """
    return {
        "status": "healthy",
        "service": "av-ethics-backend"
    }


# Main entry point for running with uvicorn
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8010,
        reload=True,  # Auto-reload on code changes
        log_level="info"
    )
