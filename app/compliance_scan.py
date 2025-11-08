# app/compliance_scan.py
from datetime import datetime
import random

def run_compliance_scan():
    findings = []
    for i in range(random.randint(2, 6)):
        findings.append({
            "user": f"user_{random.randint(100,999)}",
            "risk_score": random.randint(20, 95),
            "reason": random.choice([
                "Large withdrawal anomaly",
                "Unusual margin leverage",
                "Frequent position flipping",
                "Rapid profit accumulation"
            ]),
            "timestamp": datetime.utcnow().isoformat()
        })
    return {"scan_time": datetime.utcnow().isoformat(), "findings": findings}
