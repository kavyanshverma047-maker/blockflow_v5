#!/usr/bin/env python3
import time, os, requests

URL = os.environ.get("KEEP_ALIVE_URL", "https://blockflow-backend.onrender.com/api/health")
SLEEP = int(os.environ.get("KEEP_ALIVE_INTERVAL", "240"))

def main():
    print("Keep-alive pinging:", URL)
    while True:
        try:
            r = requests.get(URL, timeout=10)
            print("Ping:", r.status_code)
        except Exception as e:
            print("Ping failed:", e)
        time.sleep(SLEEP)

if __name__ == "__main__":
    main()
