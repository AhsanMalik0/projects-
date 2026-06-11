from abc import ABC, abstractmethod


class TelephonyProvider(ABC):
    @abstractmethod
    async def initiate_call(self, to_number: str, webhook_url: str) -> str:
        """Dial to_number. Returns external call ID from the provider."""

    @abstractmethod
    async def end_call(self, call_id: str) -> bool:
        """Hang up a live call. Returns True on success."""

    @abstractmethod
    async def get_call_status(self, call_id: str) -> str:
        """Return call status string: queued | ringing | in-progress | completed | failed."""


def get_telephony_provider(
    provider_name: str,
    account_sid: str,
    auth_token: str,
    phone_number: str,
) -> TelephonyProvider:
    """Factory that returns the correct provider with per-tenant credentials.

    Every provider receives the credentials as constructor arguments.
    No provider reads from get_settings() — all credentials come from
    the tenant record, allowing every business to use their own account.
    """
    if provider_name == "twilio":
        from app.services.telephony.twilio import TwilioTelephony
        return TwilioTelephony(account_sid, auth_token, phone_number)

    elif provider_name == "signalwire":
        from app.services.telephony.signalwire import SignalWireTelephony
        return SignalWireTelephony(account_sid, auth_token, phone_number)

    elif provider_name == "telnyx":
        from app.services.telephony.telnyx import TelnyxTelephony
        return TelnyxTelephony(account_sid, auth_token, phone_number)

    elif provider_name == "vonage":
        from app.services.telephony.vonage import VonageTelephony
        return VonageTelephony(account_sid, auth_token, phone_number)

    raise ValueError(f"Unknown telephony provider: {provider_name!r}")