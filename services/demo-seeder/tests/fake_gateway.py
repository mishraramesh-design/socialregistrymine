"""A tiny stand-in for api-gateway, used only by test_demo_seeder.py to check
demo-seeder's own state machine (running/completed/failed, 409 on concurrent
start) without needing the full platform up. `/api/consent/purposes` sleeps
briefly so a test can catch demo-seeder mid-run and assert the 409.
"""

import time

from fastapi import FastAPI

app = FastAPI()


@app.post("/api/consent/purposes")
def purposes():
    time.sleep(2.0)
    return {"code": "x"}
