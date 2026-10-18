import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.database import engine, Base
from app.limiter import limiter
from app.routes import trainee, followup, employer, analytics, ml_routes, integrations

# Create tables if not present
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Kshamata-Setu API",
    description="SIH26135 National-Finale MVP — Trainee Outcome Tracking & Skill-Gap Intelligence",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# SlowAPI Rate Limiter integration
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Middleware (Configured wildcard for demo stability; restrict origins in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to ['https://your-domain.gov.in'] for production hardening
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files Directory
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include Routers
app.include_router(trainee.router)
app.include_router(followup.router)
app.include_router(employer.router)
app.include_router(analytics.router)
app.include_router(ml_routes.router)
app.include_router(integrations.router)

# Frontend Page Routes (Zero-build direct HTML serving)
@app.get("/", include_in_schema=False)
def serve_home():
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.get("/dashboard", include_in_schema=False)
def serve_dashboard():
    return FileResponse(str(STATIC_DIR / "dashboard.html"))

@app.get("/integrations-ui", include_in_schema=False)
def serve_integrations_ui():
    return FileResponse(str(STATIC_DIR / "integrations.html"))

@app.get("/employer-view", include_in_schema=False)
def serve_employer_view():
    return FileResponse(str(STATIC_DIR / "employer_confirm.html"))

@app.get("/health")
def health_check():
    return {
        "status": "HEALTHY",
        "service": "Kshamata-Setu Backend",
        "team": "HexaCore",
        "problem_statement": "SIH26135",
        "mode": "PROTOTYPE_SIMULATION_ACTIVE",
        "notice": "Synthetic data and mock adapters only. No live government API or real trainee PII is used."
    }
