from fastapi import APIRouter
import psycopg2, sqlite3, os
from datetime import datetime

router = APIRouter(prefix="/api/system", tags=["System"])

FALLBACK_DB = os.path.join(os.getcwd(),"demo_fallback.db")

def render_info():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users;")
    u = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM spot_trades;")
    s = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM futures_usdm_trades;")
    f = cur.fetchone()[0]

    conn.close()
    return u,s,f

def fallback_info():
    if not os.path.exists(FALLBACK_DB):
        return 0,0,0
    conn = sqlite3.connect(FALLBACK_DB)
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM users;"); u = cur.fetchone()[0]
    except: u=0
    try:
        cur.execute("SELECT COUNT(*) FROM spot_trades;"); s = cur.fetchone()[0]
    except: s=0
    try:
        cur.execute("SELECT COUNT(*) FROM futures_usdm_trades;"); f = cur.fetchone()[0]
    except: f=0
    conn.close()
    return u,s,f

@router.get("/stats")
def stats():
    ru, rs, rf = render_info()
    fu, fs, ff = fallback_info()
    return {
        "render_users": ru,
        "fallback_users": fu,
        "total_users": ru+fu,
        "render_spot": rs,
        "render_futures": rf,
        "fallback_spot": fs,
        "fallback_futures": ff,
        "time": datetime.utcnow().isoformat()
    }
