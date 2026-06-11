import httpx

from app.services.telephony.base import TelephonyProvider
from app.utils.logging import get_logger

log = get_logger(__name__)


class SignalWireTelephony(TelephonyProvider):
    """SignalWire telephony provider.

    100% Twilio-API-compatible — only the base URL is different.
    account_sid  = SignalWire Project ID
    auth_token   = SignalWire API Token
    phone_number = your SignalWire phone number in E.164 format

    The space_name is embedded in account_sid as 'space_name:project_id'
    or passed separately. If account_sid contains ':' the part before it
    is used as the space name.
    """

    def __init__(self, account_sid: str, auth_token: str, phone_number: str) -> None:
        if ":" in account_sid:
            self.space_name, self.project_id = account_sid.split(":", 1)
        else:
            self.space_name = account_sid
            self.project_id = account_sid
        self.auth_token = auth_token
        self.from_number = phone_number
        self._base = f"https://{self.space_name}.signalwire.com/api/laml/2010-04-01"

    async def initiate_call(self, to_number: str, webhook_url: str) -> str:
        url = f"{self._base}/Accounts/{self.project_id}/Calls.json"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                auth=(self.project_id, self.auth_token),
                data={"To": to_number, "From": self.from_number, "Url": webhook_url},
                timeout=15,
            )
            response.raise_for_status()
            call_id = response.json().get("sid", "")
            log.info("signalwire_call_initiated", to=to_number, sid=call_id)
            return call_id

    async def end_call(self, call_id: str) -> bool:
        url = f"{self._base}/Accounts/{self.project_id}/Calls/{call_id}.json"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                auth=(self.project_id, self.auth_token),
                data={"Status": "completed"},
                timeout=10,
            )
            return response.status_code == 200

    async def get_call_status(self, call_id: str) -> str:
        url = f"{self._base}/Accounts/{self.project_id}/Calls/{call_id}.json"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                auth=(self.project_id, self.auth_token),
                timeout=10,
            )
            response.raise_for_status()
            return response.json().get("status", "unknown")