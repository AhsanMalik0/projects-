from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CallConnection:
    call_sid: str
    from_number: str
    to_number: str
    status: str


class TelephonyProvider(ABC):
    @abstractmethod
    async def initiate_call(
        self,
        to_number: str,
        from_number: str,
        webhook_url: str,
    ) -> CallConnection:
        """Place an outbound call."""

    @abstractmethod
    async def end_call(self, call_sid: str) -> bool:
        """Hang up an active call."""

    @abstractmethod
    async def get_call_status(self, call_sid: str) -> str:
        """Get current call status."""


def get_telephony_provider(provider_name: str = "twilio") -> TelephonyProvider:
    if provider_name == "twilio":
        from app.services.telephony.twilio import TwilioTelephony

        return TwilioTelephony()
    raise ValueError(f"Unknown telephony provider: {provider_name}")
