import os
from fastapi import Header
import hashlib
import secrets
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session
from database import Base, engine, get_db
from models import Customer, Campaign, TrackingLink, Scan
import io
import qrcode
from fastapi.responses import StreamingResponse

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

if not ADMIN_API_KEY:
    raise RuntimeError("ADMIN_API_KEY is not set")

app = FastAPI(
    title="Neopak QR Tracking",
    docs_url=None,
    redoc_url=None,
)


def verify_admin(
    x_admin_key: str = Header(...)
):
    if x_admin_key != ADMIN_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid admin key",
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

class TrackingLinkUpdate(BaseModel):
    destination_url: HttpUrl

def generate_code():
    return secrets.token_urlsafe(6)


class TrackingLinkUpdate(BaseModel):
    destination_url: HttpUrl

@app.get("/")
def home():
    return {
        "status": "Neopak QR Tracking running"
    }


@app.post("/admin/customers")
def create_customer(
    data: CustomerCreate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
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
    _: None = Depends(verify_admin),
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
    _: None = Depends(verify_admin),
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
    _: None = Depends(verify_admin),
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
    _: None = Depends(verify_admin),
):
    links = (
        db.query(TrackingLink)
        .order_by(TrackingLink.id.desc())
        .all()
    )

    results = []

    for link in links:

        scan_count = (
            db.query(Scan)
            .filter(
                Scan.tracking_link_id
                == link.id
            )
            .count()
        )

        campaign = link.campaign

        customer = (
            campaign.customer
            if campaign
            else None
        )

        results.append({
            "id":
                link.id,

            "code":
                link.code,

            "tracking_url":
                f"https://go.neopak.com.au/{link.code}",

            "campaign_id":
                link.campaign_id,

            "campaign_name":
                (
                    campaign.name
                    if campaign
                    else None
                ),

            "customer_id":
                (
                    customer.id
                    if customer
                    else None
                ),

            "customer_name":
                (
                    customer.business_name
                    if customer
                    else None
                ),

            "destination_url":
                link.destination_url,

            "active":
                link.active,

            "scan_count":
                scan_count,

            "created_at":
                link.created_at,
        })

    return results

@app.get("/admin/links/{link_id}/qr")
def generate_qr(
    link_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    link = db.get(
        TrackingLink,
        link_id
    )

    if not link:

        raise HTTPException(
            status_code=404,
            detail="Tracking link not found",
        )

    tracking_url = (
        f"https://go.neopak.com.au/{link.code}"
    )

    qr = qrcode.QRCode(
        version=None,
        error_correction=
            qrcode.constants.ERROR_CORRECT_M,
        box_size=12,
        border=4,
    )

    qr.add_data(
        tracking_url
    )

    qr.make(
        fit=True
    )

    image = qr.make_image(
        fill_color="black",
        back_color="white",
    )

    buffer = io.BytesIO()

    image.save(
        buffer,
        format="PNG"
    )

    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="image/png",
        headers={
            "Content-Disposition":
                f'attachment; filename="{link.code}.png"'
        },
    )


@app.patch("/admin/links/{link_id}")
def update_tracking_link(
    link_id: int,
    data: TrackingLinkUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    link = db.get(
        TrackingLink,
        link_id
    )

    if not link:

        raise HTTPException(
            status_code=404,
            detail="Tracking link not found",
        )

    link.destination_url = str(
        data.destination_url
    )

    db.commit()

    db.refresh(link)

    return {
        "id":
            link.id,

        "code":
            link.code,

        "tracking_url":
            f"https://go.neopak.com.au/{link.code}",

        "destination_url":
            link.destination_url,
    }

@app.get("/admin/campaigns")
def list_campaigns(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    campaigns = (
        db.query(Campaign)
        .order_by(Campaign.id.desc())
        .all()
    )

    return [
        {
            "id": campaign.id,
            "customer_id": campaign.customer_id,
            "name": campaign.name,
            "created_at": campaign.created_at,
        }
        for campaign in campaigns
    ]

@app.get("/admin/scans")
def list_scans(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    scans = (
        db.query(Scan)
        .order_by(Scan.scanned_at.desc())
        .all()
    )

    results = []

    for scan in scans:

        link = scan.tracking_link

        campaign = (
            link.campaign
            if link
            else None
        )

        customer = (
            campaign.customer
            if campaign
            else None
        )

        results.append({
            "id":
                scan.id,

            "tracking_link_id":
                scan.tracking_link_id,

            "code":
                (
                    link.code
                    if link
                    else None
                ),

            "campaign_name":
                (
                    campaign.name
                    if campaign
                    else None
                ),

            "customer_name":
                (
                    customer.business_name
                    if customer
                    else None
                ),

            "scanned_at":
                scan.scanned_at,

            "ip_hash":
                scan.ip_hash,

            "user_agent":
                scan.user_agent,
        })

    return results

@app.get("/admin/links/{link_id}/qr")
def generate_qr(
    link_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    link = db.get(
        TrackingLink,
        link_id
    )

    if not link:

        raise HTTPException(
            status_code=404,
            detail="Tracking link not found",
        )

    tracking_url = (
        f"https://go.neopak.com.au/{link.code}"
    )

    qr = qrcode.QRCode(
        version=None,
        error_correction=
            qrcode.constants.ERROR_CORRECT_M,
        box_size=12,
        border=4,
    )

    qr.add_data(
        tracking_url
    )

    qr.make(
        fit=True
    )

    image = qr.make_image(
        fill_color="black",
        back_color="white",
    )

    buffer = io.BytesIO()

    image.save(
        buffer,
        format="PNG"
    )

    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="image/png",
        headers={
            "Content-Disposition":
                f'attachment; filename="{link.code}.png"'
        },
    )
@app.delete("/admin/links/{link_id}")
def delete_tracking_link(
    link_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    link = db.get(TrackingLink, link_id)

    if not link:
        raise HTTPException(
            status_code=404,
            detail="Tracking link not found",
        )

    code = link.code

    db.delete(link)
    db.commit()

    return {
        "success": True,
        "message": f"Tracking link {code} deleted",
    }

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

