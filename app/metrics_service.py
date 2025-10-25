# app/metrics_service.py
from fastapi import APIRouter
from simulator import metrics_data

router = APIRouter(prefix="/api/metrics", tags=["Metrics"])

@router.get("/")
def get_metrics():
    """
    Returns live system metrics simulated by the background telemetry engine.
    """
    try:
        if metrics_data and isinstance(metrics_data, dict):
            return {
                "status": "ok",
                "data": metrics_data
            }
        else:
            return {
                "status": "initializing",
                "message": "Metrics simulation warming up — please retry in a few seconds."
            }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
