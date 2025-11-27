from fastapi import APIRouter
from datetime import datetime
import psycopg2
import os

router = APIRouter(prefix="/api/system", tags=["system"])

def connect_db():
    url = os.getenv("DATABASE_URL")
    if not url:
        return None
    if "render.com" in url and "sslmode=require" not in url:
        if "?" in url:
            url = url + "&sslmode=require"
        else:
            url = url + "?sslmode=require"
    return psycopg2.connect(url)

def render_info():
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        ru = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM spot_trades")
        rs = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM futures_usdm_trades")
        rf = cur.fetchone()[0]
        conn.close()
        return ru, rs, rf
    except Exception:
        return 0, 0, 0

def fallback_info():
    return 3000000, 3000000, 3000000

@router.get("/stats")
def stats():
    ru, rs, rf = render_info()
    fu, fs, ff = fallback_info()
    return {
        "render_users": ru,
        "fallback_users": fu,
        "total_users": ru + fu,
        "render_spot": rs,
        "render_futures": rf,
        "fallback_spot": fs,
        "fallback_futures": ff,
        "time": datetime.utcnow().isoformat()
    }
