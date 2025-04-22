import datetime

from app.celery_admin.workers.config import celery_app
from lib.dates import total_seconds

from processing.data_producers.forms.accrual_doc import \
    get_balance_by_accrual_doc
from app.caching.models.filters import FilterCache, FilterPreparedData


@celery_app.task(
    bind=True,
    rate_limit="100/s",
    max_retries=7,
    soft_time_limit=total_seconds(seconds=180),
    default_retry_delay=30
)
def prepare_accrual_doc_data(self, filter_id):
    filt = FilterCache.objects(pk=filter_id).get()
    FilterCache.objects(pk=filter_id).update_one(
        push__readiness='doc_data',
        set__used=datetime.datetime.now(),
    )


@celery_app.task(
    bind=True,
    rate_limit="100/s",
    max_retries=7,
    soft_time_limit=total_seconds(seconds=180),
    default_retry_delay=30
)
def prepare_accounts_balance(self, filter_id):
    filt = FilterCache.objects(pk=filter_id).get()
    data = get_balance_by_accrual_doc(
        filt.provider.id, filt.extra['doc_id'], accounts=filt.objs)
    d = datetime.datetime.now()
    FilterPreparedData(
        filter_id=filter_id,
        code='balance',
        data=[{'sector': k, 'data': v} for k, v in data.items()],
        created=d,
        used=d,
    ).save()
    FilterCache.objects(pk=filter_id).update_one(
        push__readiness='balance',
        set__used=datetime.datetime.now(),
    )
