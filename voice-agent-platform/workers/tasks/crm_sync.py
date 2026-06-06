import httpx

from app.utils.logging import get_logger
from workers.celery_app import celery_app

log = get_logger(__name__)


@celery_app.task(bind=True, max_retries=3)
def sync_to_crm(
    self,  # type: ignore[no-untyped-def]
    tenant_id: str,
    call_id: str,
    crm_endpoint: str,
    payload: dict,
) -> bool:
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(crm_endpoint, json=payload)
            response.raise_for_status()

        log.info(
            "crm_sync_success",
            tenant_id=tenant_id,
            call_id=call_id,
            status_code=response.status_code,
        )
        return True
    except Exception as exc:
        log.error("crm_sync_error", tenant_id=tenant_id, call_id=call_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)
