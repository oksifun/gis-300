import multiprocessing
from datetime import timedelta

import settings


def total_seconds(**kwargs):
    return int(timedelta(**kwargs).total_seconds())


CELERY_CONFIG = dict(
    broker_url=settings.S300_BROKER_URL,
    broker_transport_options={'visibility_timeout': total_seconds(hours=24)},

    # keep results separately
    result_backend=f"{settings.S300_BROKER_URL}/"
                   f"{settings.S300_CELERY_REDIS_DB}",
    # keep results 1 week
    result_expires=total_seconds(days=2),
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
    task_soft_time_limit=total_seconds(minutes=15),
    beat_schedule={},
    task_routes={}
)
