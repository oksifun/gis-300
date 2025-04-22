from datetime import datetime
import requests

import settings
from app.celery_admin.workers.config import celery_app


@celery_app.task(
    max_retries=5,
    soft_time_limit=25,
)
def qr_verification_call(task_id, phone_number):
    from app.public.models.public_dialing import PublicPayCall
    call_url = settings.QR_CALL_URL.format(phone_number)
    call_task = PublicPayCall.objects.get(id=task_id)
    send_request(call_url)
    call_task.call_date = datetime.now()
    call_task.save()


def send_request(call_url):
    try:
        response = requests.get(call_url, timeout=10)
    except requests.exceptions.Timeout:
        return dict(status="fail by timeout.")
    result = dict(status="success") if \
        response.status_code == requests.codes.ok else dict(status="fail")
    return result
