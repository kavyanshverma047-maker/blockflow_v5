#!/usr/bin/env python3
import os, sys, time, random, string
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import execute_values

DEMO_USERS = 500_000
TOTAL_SPOT = 600_000
TOTAL_FUTURES = 650_000
USER_BATCH = 2000
TRADE_BATCH = 5000
MAX_RETRIES = 5
RETRY_SLEEP = 2
PAIRS = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT"]

NOW = datetime.utcnow()
DAYS_SPAN = 180
DB_URL = os.getenv("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DB_URL)

def rnd_username():
    return "demo_" + "".join(random.choices(string.ascii_lowercase+string.digits, k=9))

def rnd_email(u):
    return f"{u}@demo.local"

def rand_price(pair):
    base = {"BTCUSDT":50000, "ETHUSDT":3000, "SOLUSDT":150, "BNBUSDT":350, "XRPUSDT":0.5}.get(pair,1000)
    return round(base*(1+random.uniform(-0.05,0.05)),8)

def rand_amount(pair):
    if pair.startswith("BTC"): return round(random.uniform(0.00005,0.015),8)
    if pair.startswith("ETH"): return round(random.uniform(0.0005,0.5),8)
    if pair.startswith("SOL"): return round(random.uniform(0.01,5),8)
    if pair.startswith("BNB"): return round(random.uniform(0.01,3),8)
    return round(random.uniform(1,1000),8)

def rand_ts():
    return (NOW - timedelta(days=random.randint(0,DAYS_SPAN))).replace(microsecond=random.randint(0,999999))

def insert_users(conn,count):
    created=0
    sql = """
    INSERT INTO users (username,email,hashed_password,balance_inr,balance_usdt,is_active,is_admin,created_at,updated_at)
    VALUES %s"""
    while created<count:
        chunk=min(USER_BATCH,count-created)
        rows=[]
        for _ in range(chunk):
            u=rnd_username()
            rows.append((u,rnd_email(u),"hash",0,0,True,False,NOW,NOW))
        tries=0
        while True:
            try:
                with conn.cursor() as cur:
                    execute_values(cur,sql,rows,page_size=1000)
                conn.commit()
                break
            except Exception as e:
                conn.rollback(); tries+=1
                if tries>MAX_RETRIES: raise
                print("Retry users:",e); time.sleep(RETRY_SLEEP)
        created+=chunk
        print(f"Users inserted: {created}/{count}")

def seed():
    conn=get_conn()
    print("Seeding users...")
    insert_users(conn,DEMO_USERS)

    print("Fetching usernames...")
    with conn.cursor() as cur:
        cur.execute("SELECT username FROM users ORDER BY id")
        users=[x[0] for x in cur.fetchall()]

    real_users = users[:3]
    demo_users = users[3:]

    def insert_trade_batch(table, rows):
        tries=0
        sql = ("INSERT INTO spot_trades (username,pair,side,price,amount,timestamp) VALUES %s"
               if table=="spot" else
               "INSERT INTO futures_usdm_trades (username,pair,side,price,amount,leverage,pnl,timestamp) VALUES %s")
        while True:
            try:
                with conn.cursor() as cur:
                    execute_values(cur, sql, rows, page_size=2000)
                conn.commit()
                return
            except Exception as e:
                conn.rollback(); tries+=1
                if tries>MAX_RETRIES: raise
                print("Retry:",e); time.sleep(RETRY_SLEEP)

    def generate(table, total):
        print(f"Inserting {table} trades: {total}")
        inserted=0
        while inserted<total:
            chunk=min(TRADE_BATCH,total-inserted)
            rows=[]
            for _ in range(chunk):
                u = random.choice(users)
                pair=random.choice(PAIRS)
                price=rand_price(pair)
                amt=rand_amount(pair)
                side=random.choice(["buy","sell"])
                ts=rand_ts()
                if table=="spot":
                    rows.append((u,pair,side,price,amt,ts))
                else:
                    lev=round(random.uniform(1,20),2)
                    pnl=round(random.uniform(-0.1,0.3)*amt*price,8)
                    rows.append((u,pair,side,price,amt,lev,pnl,ts))
            insert_trade_batch(table,rows)
            inserted+=chunk
            if inserted%20000==0:
                print(f"{table}: {inserted}/{total}")

    generate("spot",TOTAL_SPOT)
    generate("futures",TOTAL_FUTURES)

    print("Done seeding!")
    conn.close()

if __name__=="__main__":
    seed()
