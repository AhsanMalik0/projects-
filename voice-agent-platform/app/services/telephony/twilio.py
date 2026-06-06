import httpx

from app.config import get_settings
from app.services.telephony.base import CallConnection, TelephonyProvider
from app.utils.logging import get_logger

log = get_logger(__name__)

TWILIO_API = "https://api.twilio.com/2010-04-01"


class TwilioTelephony(TelephonyProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.from_number = settings.twilio_phone_number

    async def initiate_call(
        self,
        to_number: str,
        from_number: str,
        webhook_url: str,
    ) -> CallConnection:
        url = f"{TWILIO_API}/Accounts/{self.account_sid}/Calls.json"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                auth=(self.account_sid, self.auth_token),
                data={
                    "To": to_number,
                    "From": from_number or self.from_number,
                    "Url": webhook_url,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        log.info("twilio_call_initiated", call_sid=data["sid"], to=to_number)
        return CallConnection(
            call_sid=data["sid"],
            from_number=data.get("from", from_number),
            to_number=to_number,
            status=data.get("status", "queued"),
        )

    async def end_call(self, call_sid: str) -> bool:
        url = f"{TWILIO_API}/Accounts/{self.account_sid}/Calls/{call_sid}.json"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                auth=(self.account_sid, self.auth_token),
                data={"Status": "completed"},
            )
        log.info("twilio_call_ended", call_sid=call_sid, status=resp.status_code)
        return resp.status_code == 200

    async def get_call_status(self, call_sid: str) -> str:
        url = f"{TWILIO_API}/Accounts/{self.account_sid}/Calls/{call_sid}.json"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                auth=(self.account_sid, self.auth_token),
            )
            resp.raise_for_status()
            return resp.json().get("status", "unknown")
