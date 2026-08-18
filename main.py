from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from datetime import datetime

app = FastAPI()

# Temporary links until database is added
LINKS = {
    "test123": "https://www.google.com",
}


@app.get("/")
def home():
    return {
        "status": "Neopak QR Tracking running"
    }


@app.get("/{code}")
def track(code: str):
    destination = LINKS.get(code)

    if not destination:
        return {
            "error": "Tracking link not found"
        }

    print(
        f"QR SCAN | {code} | {datetime.utcnow()}"
    )

    return RedirectResponse(
        destination,
        status_code=302
    )