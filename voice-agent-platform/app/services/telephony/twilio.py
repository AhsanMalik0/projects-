import httpx

from app.services.telephony.base import TelephonyProvider
from app.utils.logging import get_logger

log = get_logger(__name__)

TWILIO_API = "https://api.twilio.com/2010-04-01"


class TwilioTelephony(TelephonyProvider):
    """Twilio telephony provider using per-tenant credentials."""

    def __init__(self, account_sid: str, auth_token: str, phone_number: str) -> None:
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = phone_number

    async def initiate_call(self, to_number: str, webhook_url: str) -> str:
        url = f"{TWILIO_API}/Accounts/{self.account_sid}/Calls.json"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                auth=(self.account_sid, self.auth_token),
                data={
                    "To": to_number,
                    "From": self.from_number,
                    "Url": webhook_url,
                    "Method": "GET",
                },
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            call_sid = data.get("sid", "")
            log.info("twilio_call_initiated", to=to_number, sid=call_sid)
            return call_sid

    async def end_call(self, call_id: str) -> bool:
        url = f"{TWILIO_API}/Accounts/{self.account_sid}/Calls/{call_id}.json"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                auth=(self.account_sid, self.auth_token),
                data={"Status": "completed"},
                timeout=10,
            )
            ok = response.status_code == 200
            log.info("twilio_call_ended", call_id=call_id, ok=ok)
            return ok

    async def get_call_status(self, call_id: str) -> str:
        url = f"{TWILIO_API}/Accounts/{self.account_sid}/Calls/{call_id}.json"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                auth=(self.account_sid, self.auth_token),
                timeout=10,
            )
            response.raise_for_status()
            return response.json().get("status", "unknown")