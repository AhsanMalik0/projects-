import time

import httpx
import jwt as pyjwt

from app.services.telephony.base import TelephonyProvider
from app.utils.logging import get_logger

log = get_logger(__name__)

VONAGE_API = "https://api.nexmo.com/v1"


class VonageTelephony(TelephonyProvider):
    """Vonage (Nexmo) telephony provider.

    account_sid  = Vonage API Key
    auth_token   = Vonage API Secret
    phone_number = your Vonage virtual number in E.164 format
    """

    def __init__(self, account_sid: str, auth_token: str, phone_number: str) -> None:
        self.api_key = account_sid
        self.api_secret = auth_token
        self.from_number = phone_number

    def _jwt_token(self) -> str:
        """Generate a short-lived JWT for Vonage API authentication."""
        payload = {
            "application_id": self.api_key,
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
            "jti": f"vonage-{int(time.time())}",
        }
        return pyjwt.encode(payload, self.api_secret, algorithm="HS256")

    async def initiate_call(self, to_number: str, webhook_url: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{VONAGE_API}/calls",
                headers={
                    "Authorization": f"Bearer {self._jwt_token()}",
                    "Content-Type": "application/json",
                },
                json={
                    "to": [{"type": "phone", "number": to_number.lstrip("+")}],
                    "from": {"type": "phone", "number": self.from_number.lstrip("+")},
                    "answer_url": [webhook_url],
                    "answer_method": "GET",
                },
                timeout=15,
            )
            response.raise_for_status()
            call_id = response.json().get("uuid", "")
            log.info("vonage_call_initiated", to=to_number, uuid=call_id)
            return call_id

    async def end_call(self, call_id: str) -> bool:
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{VONAGE_API}/calls/{call_id}",
                headers={
                    "Authorization": f"Bearer {self._jwt_token()}",
                    "Content-Type": "application/json",
                },
                json={"action": "hangup"},
                timeout=10,
            )
            ok = response.status_code in (200, 204)
            log.info("vonage_call_ended", call_id=call_id, ok=ok)
            return ok

    async def get_call_status(self, call_id: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{VONAGE_API}/calls/{call_id}",
                headers={"Authorization": f"Bearer {self._jwt_token()}"},
                timeout=10,
            )
            response.raise_for_status()
            return response.json().get("status", "unknown")