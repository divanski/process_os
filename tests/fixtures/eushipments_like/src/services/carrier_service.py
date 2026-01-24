"""
Carrier Service
eushipments_like fixture

Handles carrier API interactions for shipment creation, labels, and rates.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..models.shipment import Address, Package, Shipment


@dataclass
class RateQuote:
    """Rate quote from carrier."""

    carrier_id: str
    service_type: str
    amount: float
    currency: str
    estimated_days: int
    guaranteed: bool = False


@dataclass
class LabelResult:
    """Label generation result."""

    tracking_number: str
    label_url: str
    label_format: str
    carrier_id: str


class CarrierAdapter(ABC):
    """Abstract base class for carrier adapters."""

    @abstractmethod
    def create_shipment(
        self,
        sender: Address,
        recipient: Address,
        packages: List[Package],
    ) -> Shipment:
        """Create a shipment with the carrier."""
        pass

    @abstractmethod
    def get_rates(
        self,
        sender: Address,
        recipient: Address,
        packages: List[Package],
    ) -> List[RateQuote]:
        """Get shipping rates."""
        pass

    @abstractmethod
    def generate_label(self, shipment_id: str) -> LabelResult:
        """Generate shipping label."""
        pass


class DHLAdapter(CarrierAdapter):
    """DHL carrier adapter."""

    CARRIER_ID = "dhl"

    def __init__(self, api_key: str, base_url: str):
        """Initialize DHL adapter."""
        self.api_key = api_key
        self.base_url = base_url

    def create_shipment(
        self,
        sender: Address,
        recipient: Address,
        packages: List[Package],
    ) -> Shipment:
        """Create DHL shipment."""
        # Implementation would call DHL API
        raise NotImplementedError("DHL integration pending")

    def get_rates(
        self,
        sender: Address,
        recipient: Address,
        packages: List[Package],
    ) -> List[RateQuote]:
        """Get DHL rates."""
        # Implementation would call DHL API
        raise NotImplementedError("DHL integration pending")

    def generate_label(self, shipment_id: str) -> LabelResult:
        """Generate DHL label."""
        # Implementation would call DHL API
        raise NotImplementedError("DHL integration pending")


class CarrierService:
    """
    Main carrier service orchestrating multiple carriers.

    Handles carrier selection, fallback, and rate comparison.
    """

    def __init__(self, carriers_config: Dict[str, Any]):
        """Initialize with carrier configuration."""
        self.config = carriers_config
        self.adapters: Dict[str, CarrierAdapter] = {}

    def register_adapter(self, carrier_id: str, adapter: CarrierAdapter) -> None:
        """Register a carrier adapter."""
        self.adapters[carrier_id] = adapter

    def get_best_rate(
        self,
        sender: Address,
        recipient: Address,
        packages: List[Package],
        carriers: Optional[List[str]] = None,
    ) -> Optional[RateQuote]:
        """Get best rate across carriers."""
        all_rates: List[RateQuote] = []

        target_carriers = carriers or list(self.adapters.keys())

        for carrier_id in target_carriers:
            adapter = self.adapters.get(carrier_id)
            if adapter:
                try:
                    rates = adapter.get_rates(sender, recipient, packages)
                    all_rates.extend(rates)
                except Exception:
                    continue

        if not all_rates:
            return None

        return min(all_rates, key=lambda r: r.amount)

    def create_shipment(
        self,
        carrier_id: str,
        sender: Address,
        recipient: Address,
        packages: List[Package],
    ) -> Shipment:
        """Create shipment with specified carrier."""
        adapter = self.adapters.get(carrier_id)
        if not adapter:
            raise ValueError(f"Carrier not configured: {carrier_id}")

        return adapter.create_shipment(sender, recipient, packages)
