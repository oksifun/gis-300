import logging
from datetime import timedelta
from bson import ObjectId
from typing import (
    Union,
)

from mongoengine import (
    Q,
)

from app.celery_admin.workers.config import celery_app
from app.requests.models.request import Request
from app.telephony.models.choices import Result
from app.telephony.models.base_fields import RequestEmbedded
from app.telephony.models.call_log_history import Calls

logger = logging.getLogger('c300')


@celery_app.task(
    bind=True,
    max_retries=3,
    soft_time_limit=5 * 60,
    retry_backoff=True,
)
def bind_related_calls_after_request_save_task(
        self,
        request_id: Union[ObjectId, str],
        hours_before: int = 24,
):
    """
        Функция связывания заявок со звонками и наоборот, если заявка была
            создана не из карточки звонка, вызывается при сохранении заявки

    Args:
        self: task instance
        request_id: Request id (заявка)
        hours_before: в пределах скольки часов до создания заявки ищем
            звонки для связки с заявками
    """
    request = Request.objects.get(id=request_id)
    query = (
        Q(result__in=[Result.ANSWER])
        & Q(calldate__gte=request.created_at - timedelta(hours=hours_before))
        & (
            (
                    Q(src_caller__id=request.tenant.id)
                    & Q(dst_answering__id=request.dispatcher.id)
            )
            | (
                    Q(src_caller__id=request.dispatcher.id)
                    & Q(dst_answering__id=request.tenant.id)
            )
        )
    )
    related_calls = Calls.objects(query).all()
    request_related_call_ids_set = set(request.related_call_ids)
    for call in related_calls:
        call_requests_set = set(call.requests)
        call_requests_set.add(
            RequestEmbedded(id=request.id, body=request.body)
        )
        call.update(requests=list(call_requests_set))
        request_related_call_ids_set.add(call.id)
    request.update(related_call_ids=list(request_related_call_ids_set))
    return 'success'
