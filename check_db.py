import sqlite3, os

DBS = ["blockflow.db", "demo_fallback.db"]

for db in DBS:
    if not os.path.exists(db):
        print(f"\n[SKIP] {db} not found.")
        continue

    print(f"\n========= {db} =========")

    conn = sqlite3.connect(db)
    cur = conn.cursor()

    print("\n--- TABLE SCHEMA ---")
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cur.fetchall()]

    for t in tables:
        print(f"\nTable: {t}")
        cur.execute(f"PRAGMA table_info({t});")
        for col in cur.fetchall():
            print(col)

    print("\n--- ROW COUNTS ---")
    for t in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t};")
            print(f"{t}: {cur.fetchone()[0]}")
        except:
            print(f"{t}: ERROR")

    conn.close()
