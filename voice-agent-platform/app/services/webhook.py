import json

import httpx

from app.utils.auth import sign_webhook_payload
from app.utils.logging import get_logger

log = get_logger(__name__)


async def deliver_webhook(
    url: str,
    payload: dict,
    secret: str,
    timeout: float = 10.0,
) -> bool:
    body = json.dumps(payload).encode()
    signature = sign_webhook_payload(body, secret)

    headers = {
        "Content-Type": "application/json",
        "X-Signature-SHA256": signature,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, content=body, headers=headers)
            resp.raise_for_status()
        log.info("webhook_delivered", url=url, status=resp.status_code)
        return True
    except Exception as exc:
        log.error("webhook_delivery_failed", url=url, error=str(exc))
        return False
