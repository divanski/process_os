"""
Shipment Model
eushipments_like fixture
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class ShipmentStatus(Enum):
    """Shipment status values."""

    PENDING = "pending"
    LABEL_CREATED = "label_created"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    EXCEPTION = "exception"
    RETURNED = "returned"


@dataclass
class Address:
    """Shipping address."""

    name: str
    street1: str
    city: str
    postal_code: str
    country_code: str
    street2: Optional[str] = None
    state: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


@dataclass
class Package:
    """Package dimensions and weight."""

    weight: float  # kg
    length: float  # cm
    width: float  # cm
    height: float  # cm
    description: Optional[str] = None


@dataclass
class TrackingEvent:
    """Tracking history event."""

    timestamp: str  # ISO format
    status: ShipmentStatus
    location: str
    description: str


@dataclass
class Shipment:
    """Shipment entity."""

    shipment_id: str
    carrier_id: str
    tracking_number: Optional[str]
    status: ShipmentStatus
    sender: Address
    recipient: Address
    packages: List[Package]
    created_at: str  # ISO format
    updated_at: str  # ISO format
    tracking_events: List[TrackingEvent] = field(default_factory=list)
    label_url: Optional[str] = None
    rate_amount: Optional[float] = None
    rate_currency: str = "EUR"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "shipment_id": self.shipment_id,
            "carrier_id": self.carrier_id,
            "tracking_number": self.tracking_number,
            "status": self.status.value,
            "sender": {
                "name": self.sender.name,
                "street1": self.sender.street1,
                "street2": self.sender.street2,
                "city": self.sender.city,
                "postal_code": self.sender.postal_code,
                "country_code": self.sender.country_code,
            },
            "recipient": {
                "name": self.recipient.name,
                "street1": self.recipient.street1,
                "street2": self.recipient.street2,
                "city": self.recipient.city,
                "postal_code": self.recipient.postal_code,
                "country_code": self.recipient.country_code,
            },
            "packages": [
                {
                    "weight": p.weight,
                    "length": p.length,
                    "width": p.width,
                    "height": p.height,
                    "description": p.description,
                }
                for p in self.packages
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
