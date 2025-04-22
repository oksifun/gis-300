from celery import Celery
from celery.schedules import crontab
import multiprocessing
from datetime import timedelta
import settings


def _total_seconds(**kwargs):
    return int(timedelta(**kwargs).total_seconds())


CELERY_CONFIG = dict(
    broker_url=settings.GIS_BROKER_URL,
    broker_transport_options={'visibility_timeout': _total_seconds(hours=24)},

    # keep results separately
    result_backend=f"{settings.GIS_BROKER_URL}",
    # keep results 1 week
    result_expires=_total_seconds(days=2),
    task_serializer='pickle',
    result_serializer='json',
    accept_content=['pickle', 'json'],
    task_default_rate_limit="1000/m",
    # после обновления целери таймзона начала глючить, временно выключено
    # время запуска периодических задач также указано по гмт
    # timezone='Europe/Moscow',

    worker_pool_restarts=True,
    worker_autoscaler=True,
    worker_prefetch_multiplier=4,
    worker_concurrency=multiprocessing.cpu_count() + 1,
    task_soft_time_limit=_total_seconds(minutes=15),
    beat_schedule={},
    task_routes={}
)

_QUEUE = 'gis'

GIS_TASK_ROUTES = {  # НЕОБХОДИМЫ для всех КЛАССОВ задач = {путь.модуля}.*'
    'app.gis.tasks.*': {'queue': _QUEUE},
    'riddler.*': {'queue': _QUEUE},
    'gis.*': {'queue': _QUEUE},
}

GIS_TASK_SCHEDULE = {
    'gis-scheduled-every-n-minutes': {
        'task': 'gis.scheduled',  # (изменения) ЛС, ПУ,...
        'schedule': crontab(minute='*/44'),  # каждый 44 минуты
    },
    'gis-conducted-every-night': {
        'task': 'gis.conducted',  # ПД (AccrualDoc)
        'schedule': crontab(minute=22, hour=1),  # 04:22 MSK
    },
    'gis-resurrected-every-night': {
        'task': 'gis.resurrect',  # перезапуск задач с 500 ошибками от ГИС
        'schedule': crontab(minute=22, hour=0),  # 03:22 MSK
    },
    'gis-collected-every-day-end': {
        'task': 'gis.collected',  # показания (загрузить из ГИС ЖКХ)
        'schedule': crontab(minute=33, hour=19),  # 22:33 MSK
    },
    'gis-gathered-every-day-end': {
        'task': 'gis.gathered',  # показания (выгрузить в ГИС ЖКХ)
        'schedule': crontab(minute=33, hour=20),  # 23:33 MSK
    },
    'gis-cleanup-every-morning': {
        'task': 'gis.cleanup',
        'schedule': crontab(minute=11, hour=0),  # 03:11 MSK
    },
    'gis-reanimate-every-night': {
        'task': 'gis.reanimate',
        'schedule': crontab(minute=11, hour=4),  # 07:11 MSK
    },
}


gis_celery_app = Celery(
    include=[
        'app.gis.tasks.bills',
        'app.gis.tasks.house',
        'app.gis.tasks.metering',
        'app.gis.tasks.nsi',
        'app.gis.tasks.org',
        'app.gis.tasks.scheduled',
        'app.gis.tasks.async_operation',
    ]
)
gis_celery_app.conf.update(**CELERY_CONFIG)
gis_celery_app.conf.beat_schedule = {
    **GIS_TASK_SCHEDULE,
}
gis_celery_app.conf.task_routes = {
    **GIS_TASK_ROUTES,
}
