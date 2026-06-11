import httpx

from app.services.telephony.base import TelephonyProvider
from app.utils.logging import get_logger

log = get_logger(__name__)

TELNYX_API = "https://api.telnyx.com/v2"


class TelnyxTelephony(TelephonyProvider):
    """Telnyx telephony provider.

    account_sid  = Telnyx API Key ID (from telnyx.com → API Keys)
    auth_token   = Telnyx API Key Secret
    phone_number = your Telnyx number in E.164 format (+12025551234)
    """

    def __init__(self, account_sid: str, auth_token: str, phone_number: str) -> None:
        # Telnyx uses the secret as the Bearer token
        self.api_key = auth_token
        self.from_number = phone_number

    async def initiate_call(self, to_number: str, webhook_url: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TELNYX_API}/calls",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "to": to_number,
                    "from": self.from_number,
                    "webhook_url": webhook_url,
                    "webhook_url_method": "GET",
                },
                timeout=15,
            )
            response.raise_for_status()
            data = response.json().get("data", {})
            call_id = data.get("call_control_id", "")
            log.info("telnyx_call_initiated", to=to_number, call_control_id=call_id)
            return call_id

    async def end_call(self, call_id: str) -> bool:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TELNYX_API}/calls/{call_id}/actions/hangup",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10,
            )
            ok = response.status_code in (200, 204)
            log.info("telnyx_call_ended", call_id=call_id, ok=ok)
            return ok

    async def get_call_status(self, call_id: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{TELNYX_API}/calls/{call_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10,
            )
            response.raise_for_status()
            return response.json().get("data", {}).get("state", "unknown")