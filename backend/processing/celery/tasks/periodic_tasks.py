import datetime
import logging
from api.v4.telephony.models.history import CallHistory
from app.celery_admin.workers.config import celery_app
from processing.celery.workers.great_white_shark.cleaning_tmp import \
    clean_sber_sessions
from processing.celery.tasks.cleaning_tmp import clean_filters_cash

logger = logging.getLogger(__name__)


@celery_app.task(
    soft_time_limit=60,
    bind=True
)
def clean_cache(self):
    """
    Создаёт задачи по очистке кэша
    """
    clean_filters_cash.delay()
    clean_sber_sessions.delay()


@celery_app.task(
    soft_time_limit=60,
    bind=True,
)
def update_record_link(self, start_day=None):
    """Переименовывает урлы в журнале вызовов.

    Каждый день в 3 часа ночи записи разговоров переносяться в резервное хранилище.
    """
    finish_day = datetime.date.today() - datetime.timedelta(days=1)
    if type(start_day) == str:
        try:
            start_day = datetime.datetime.strptime(start_day, '%d.%M.%Y')
        except ValueError:
            start_day = finish_day
    elif type(start_day) in (datetime.date, datetime.datetime):
        pass
    else:
        start_day = finish_day

    start_day = datetime.datetime.combine(start_day, datetime.time.min)
    finish_day = datetime.datetime.combine(finish_day, datetime.time.max)
    calls = CallHistory.objects(
        calldate__gte=start_day,
        calldate__lte=finish_day,
        record_url__ne='',
    )
    for call in calls:
        new_url = call.record_url.replace(
            'tEyE4yGRFGVzUDOY4G5OyEoB404S3CMx',
            'wf4W649FHRvk82vsX3Wu5lUPp4S2Jk00',
        )
        call.update(record_url=new_url)
