import hashlib
import secrets

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Customer, Campaign, TrackingLink, Scan


app = FastAPI(
    title="Neopak QR Tracking",
)


Base.metadata.create_all(bind=engine)


class CustomerCreate(BaseModel):
    business_name: str


class CampaignCreate(BaseModel):
    customer_id: int
    name: str


class TrackingLinkCreate(BaseModel):
    campaign_id: int
    destination_url: HttpUrl


def generate_code():
    return secrets.token_urlsafe(6)


@app.get("/")
def home():
    return {
        "status": "Neopak QR Tracking running"
    }


@app.post("/admin/customers")
def create_customer(
    data: CustomerCreate,
    db: Session = Depends(get_db),
):
    customer = Customer(
        business_name=data.business_name,
    )

    db.add(customer)
    db.commit()
    db.refresh(customer)

    return {
        "id": customer.id,
        "business_name": customer.business_name,
    }


@app.get("/admin/customers")
def list_customers(
    db: Session = Depends(get_db),
):
    customers = db.query(Customer).all()

    return [
        {
            "id": customer.id,
            "business_name": customer.business_name,
        }
        for customer in customers
    ]


@app.post("/admin/campaigns")
def create_campaign(
    data: CampaignCreate,
    db: Session = Depends(get_db),
):
    customer = db.get(
        Customer,
        data.customer_id,
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    campaign = Campaign(
        customer_id=data.customer_id,
        name=data.name,
    )

    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    return {
        "id": campaign.id,
        "customer_id": campaign.customer_id,
        "name": campaign.name,
    }


@app.post("/admin/links")
def create_tracking_link(
    data: TrackingLinkCreate,
    db: Session = Depends(get_db),
):
    campaign = db.get(
        Campaign,
        data.campaign_id,
    )

    if not campaign:
        raise HTTPException(
            status_code=404,
            detail="Campaign not found",
        )

    while True:
        code = generate_code()

        exists = (
            db.query(TrackingLink)
            .filter(TrackingLink.code == code)
            .first()
        )

        if not exists:
            break

    tracking_link = TrackingLink(
        campaign_id=data.campaign_id,
        code=code,
        destination_url=str(data.destination_url),
    )

    db.add(tracking_link)
    db.commit()
    db.refresh(tracking_link)

    return {
        "id": tracking_link.id,
        "code": tracking_link.code,
        "tracking_url": f"https://go.neopak.com.au/{tracking_link.code}",
        "destination_url": tracking_link.destination_url,
    }


@app.get("/admin/links")
def list_links(
    db: Session = Depends(get_db),
):
    links = db.query(TrackingLink).all()

    return [
        {
            "id": link.id,
            "code": link.code,
            "campaign_id": link.campaign_id,
            "destination_url": link.destination_url,
            "active": link.active,
        }
        for link in links
    ]

@app.get("/admin/scans")
def list_scans(
    db: Session = Depends(get_db),
):
    scans = (
        db.query(Scan)
        .order_by(Scan.scanned_at.desc())
        .all()
    )

    return [
        {
            "id": scan.id,
            "tracking_link_id": scan.tracking_link_id,
            "scanned_at": scan.scanned_at,
            "ip_hash": scan.ip_hash,
            "user_agent": scan.user_agent,
        }
        for scan in scans
    ]

@app.get("/{code}")
def track(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
):
    tracking_link = (
        db.query(TrackingLink)
        .filter(TrackingLink.code == code)
        .first()
    )

    if not tracking_link:
        raise HTTPException(
            status_code=404,
            detail="Tracking link not found",
        )

    if not tracking_link.active:
        raise HTTPException(
            status_code=410,
            detail="Tracking link inactive",
        )

    ip_address = (
        request.headers.get("CF-Connecting-IP")
        or request.client.host
        if request.client
        else None
    )

    ip_hash = None

    if ip_address:
        ip_hash = hashlib.sha256(
            ip_address.encode()
        ).hexdigest()

    user_agent = request.headers.get(
        "user-agent"
    )

    scan = Scan(
        tracking_link_id=tracking_link.id,
        ip_hash=ip_hash,
        user_agent=user_agent,
    )

    db.add(scan)
    db.commit()

    return RedirectResponse(
        url=tracking_link.destination_url,
        status_code=302,
    )