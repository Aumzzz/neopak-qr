from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    business_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    campaigns = relationship(
        "Campaign",
        back_populates="customer",
        cascade="all, delete-orphan",
    )


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    customer = relationship(
        "Customer",
        back_populates="campaigns",
    )

    tracking_links = relationship(
        "TrackingLink",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )


class TrackingLink(Base):
    __tablename__ = "tracking_links"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id"),
        nullable=False,
    )

    code: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
    )

    destination_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    campaign = relationship(
        "Campaign",
        back_populates="tracking_links",
    )

    scans = relationship(
        "Scan",
        back_populates="tracking_link",
        cascade="all, delete-orphan",
    )


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    tracking_link_id: Mapped[int] = mapped_column(
        ForeignKey("tracking_links.id"),
        nullable=False,
    )

    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    ip_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    tracking_link = relationship(
        "TrackingLink",
        back_populates="scans",
    )