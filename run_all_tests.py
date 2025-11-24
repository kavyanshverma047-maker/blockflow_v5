# run_all_tests.py (auto-generated)
import requests, time

BASE = "http://127.0.0.1:8000"

def show(title, res):
    try:
        print(f"\n--- {title} ---")
        print(res.status_code, res.json())
    except:
        try:
            print(res.status_code, res.text)
        except:
            print("Unknown error")

# REGISTER
res = requests.post(f"{BASE}/api/auth/register", json={
    "username": "testuser",
    "email": "test@x.com",
    "password": "123456"
})
show("REGISTER", res)

# LOGIN
res = requests.post(f"{BASE}/api/auth/login", json={
    "username": "testuser",
    "password": "123456"
})
show("LOGIN", res)

print("\nALL TESTS DONE ✔")
