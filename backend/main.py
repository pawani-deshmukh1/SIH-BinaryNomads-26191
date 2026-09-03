from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(
    title="DISHA Backend API",
    description="Intelligent Identification of Hazard-Based Red Zones & Relocation Needs",
    version="1.0.0"
)

# Allow CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

from api import settings_api, damage, flood, landslide, red_zones, relocation, routes, towers, ground_situation, evac_zones, feedback, analyze, inundation, live_risk, susceptibility, advisory, simulation

app.include_router(settings_api.router)
app.include_router(damage.router)
app.include_router(flood.router)
app.include_router(landslide.router)
app.include_router(red_zones.router)
app.include_router(evac_zones.router)
app.include_router(relocation.router)
app.include_router(routes.router)
app.include_router(towers.router)
app.include_router(ground_situation.router)
app.include_router(feedback.router)
app.include_router(analyze.router)
app.include_router(inundation.router)
app.include_router(live_risk.router)
app.include_router(susceptibility.router)
app.include_router(advisory.router)
app.include_router(simulation.router)

# Serve the dashboard as static files at /app/
# Open http://127.0.0.1:8000/app/simulation.html?hab_id=...
DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "..", "dashboard")
app.mount("/app", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")

