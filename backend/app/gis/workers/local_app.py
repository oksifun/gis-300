import logging
from datetime import datetime, timedelta

from celery import Celery
from celery.apps.worker import Worker
# from celery.app.registry import TaskRegistry
# from celery.worker.autoscale import Autoscaler

from app.gis.workers.local_conf import *


logger = logging.getLogger(
    CELERY_APP_NAME)  # логгер Celery, используется в задачах

# Celery.on_init = init_celery  # вызывается в процессе Celery.__init__
logger.warning("Выполняется инициализация Celery...")


class CeleryConfig:
    """
    Загружается каждый раз при импорте модуля и единожды при использовании
    в качестве декоратора
    https://docs.celeryproject.org/en/latest/userguide/configuration.html
    """
    # ETA не учитывает сдвиг времени согласно временной зоне (4.1-)
    enable_utc = CELERY_ENABLE_UTC
    # временная зона для дат и времени, по умолчанию = 'UTC'
    timezone = CELERY_TIMEZONE

    # задачи ВСЕГДА выполняются синхронно (без использования очереди)
    task_always_eager = CELERY_TASK_ALWAYS_EAGER
    # СИНХРОННЫЕ задачи всегда передают исключения ~ apply(throw=True)
    task_eager_propagates = True

    # не передавать результаты (можно получить из задачи с ignore_result=False)
    task_ignore_result = False

    # подтверждать получение задачи ПОСЛЕ выполнения
    task_acks_late = False
    # подтверждать задачи с ошибкой
    task_acks_on_failure_or_timeout = task_acks_late
    # отправлять повторно, если исполнитель оставновлен
    task_reject_on_worker_lost = task_acks_late

    # 'persistent' - сохранять на диск, 'transient'  - не сохранять
    task_default_delivery_mode = 'transient'

    # отвечает за передачу сообщений (задач) между исполнителями (worker)
    broker_url = BROKER_URL
    # хранилище результатов выполнения задач (tasks)
    result_backend = CELERY_RESULT_BACKEND

    # исполнитель будет пытаться подключиться к брокеру после ошибки
    broker_connection_retry = True
    broker_connection_max_retries = 2
    broker_connection_timeout = 2  # время ожидания подключения к серверу в сек.

    # ТОЛЬКО для PyAMQP: решение TimeoutError при использовании eventlet/gevent
    # broker_heartbeat = 0
    broker_pool_limit = BROKER_POOL_LIMIT

    broker_transport_options = {
        # https://github.com/celery/kombu/blob/master/kombu/transport/redis.py
        **BROKER_TRANSPORT_OPTIONS,
        'visibility_timeout': BROKER_VISIBILITY_TIMEOUT,
        # фильтровать для исполнителей события из всех, связанных с задачами
        # 'fanout_prefix': True,

        # the fanout exchange support for patterns in routing and binding keys
        # 'fanout_patterns': True
    }

    result_backend_transport_options = {
        'visibility_timeout': BROKER_VISIBILITY_TIMEOUT,
    }

    imports = CELERY_IMPORTS
    # worker.include + app.include + tasks.__class__.__module__
    include = CELERY_INCLUDE

    task_default_queue = CELERY_TASK_DEFAULT_QUEUE
    task_create_missing_queues = (  # создавать отсутствующие очереди?
            CELERY_QUEUES is None)

    # дополнительное состояние выполнения задачи (started)
    task_track_started = False

    # direct - по названию очереди, topic - по шаблону, fanout, headers
    # task_default_exchange_type = 'direct'

    # Redis не поддерживает Exchange!
    # task_default_exchange = task_default_queue
    # task_default_routing_key = task_default_queue

    task_queues = CELERY_QUEUES
    task_routes = CELERY_ROUTES  # {**GIS_TASK_ROUTES}
    # beat_schedule = {**GIS_TASK_SCHEDULE}

    task_serializer = CELERY_TASK_SERIALIZER
    result_serializer = CELERY_RESULT_SERIALIZER
    accept_content = CELERY_ACCEPT_CONTENT

    task_time_limit = CELERYD_TASK_TIME_LIMIT
    task_soft_time_limit = CELERYD_TASK_SOFT_TIME_LIMIT

    result_expires = CELERY_TASK_RESULT_EXPIRES
    # дописывать служебную информацию?
    # (name,args,kwargs,worker,retries,queue,delivery_info)
    result_extended = False
    result_cache_max = -1  # кэширование результатов: 0 - без огр., -1 - выкл.

    task_default_rate_limit = CELERY_TASK_DEFAULT_RATE_LIMIT
    worker_disable_rate_limits = False  # отключить рейтинги задач исполнителей

    # настройки для prefork при превышении вызывают замену закончившего задачу
    # исполнителя новым! по умолчанию - безлимит
    worker_max_tasks_per_child = 9999  # макс. выполненных (в сумме) задач пула
    worker_max_memory_per_child = 999 * 1024  # макс. памяти исполнителя в Кб

    worker_pool = None \
        if CELERYD_POOL in {'eventlet', 'gevent'} else CELERYD_POOL  # WARNING

    worker_concurrency = CELERYD_CONCURRENCY
    worker_prefetch_multiplier = CELERYD_PREFETCH_MULTIPLIER
    # доп. поток Autoscaler позволяет наращивать кол-во процессов
    # пула (исполнителя) при необходимости
    # по истечению Autoscaler.keepalive сек. кол-во процессов будет уменьшено

    worker_hijack_root_logger = CELERYD_HIJACK_ROOT_LOGGER  # логирование
    # worker_log_format = \
    #     "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s"
    # worker_task_log_format = \
    #     "[%(asctime)s: %(levelname)s/%(processName)s]" \
    #     "[%(task_name)s(%(task_id)s)] %(message)s"

    worker_redirect_stdouts = CELERYD_REDIRECT_STDOUTS
    worker_redirect_stdouts_level = CELERYD_REDIRECT_STDOUTS_LEVEL


# main, loader, backend, amqp, events, log, control, namespace,
# tasks, broker, include, changes, config_source, fixups, task_cls,
# set_as_current = True, autofinalize = True, strict_typing = True, **kwargs
my_app = Celery(
    main=CELERY_APP_NAME,
    # используется при генерации названий задач, по умолчанию "__main__"
    # namespace = 'CELERY',  # префикс загружаемых параметров ~ [CELERY]_URL
    config_source=CeleryConfig,
    # config_from_object("имя файла (модуля)" или объект/класс)
    # task_cls = None,  # базовый класс для ВСЕХ задач - только для самост. app
    # tasks = None,  # TaskRegistry = dict(task_name, task_instance)
    # TaskRegistry формируется как app.tasks.register(CustomTask)
    strict_typing=True,  # валидация аргументов задач
    set_as_current=True,  # текущий экземпляр?
    autofinalize=True  # НЕ ОТКЛЮЧАТЬ! модули не загр. при ручной финализации!
    # остальные параметры передаются как kwargs
)


# app.config_from_object('django.conf:settings', namespace = 'CELERY')
# app.autodiscover_tasks([])  # используется только для django


def get_tz(override: str = None):
    from pytz import timezone

    if override:
        return timezone(override)

    if my_app.conf.get('enable_utc', False):
        return timezone('UTC')

    tz = my_app.conf.get('timezone', 'UTC')  # 'Europe/Moscow'
    if isinstance(tz, str):  # может быть tzinfo
        tz = timezone(tz)

    return tz


def dt_in_tz(**delta: float) -> datetime:
    """
    Дата и время во временной зоне Celery
    :param delta: изменение (дельта) текущих даты и времени в формате timedelta:
        days=..., seconds, microseconds, milliseconds, minutes, hours, weeks
    """
    now = datetime.now(get_tz())

    if delta:
        return now + timedelta(**delta)
    else:
        return now


def to_eta(time: tuple, date: tuple = None) -> datetime:
    """
    Estimated Time of Arrival - самое раннее время выполнения задачи
    Если задано время в прошлом, то задача выполнится при первой же возможности!
    :param time: время в формате (час, минута, секунда)
    :param date: дата в формате (год, месяц, день)
    :return: дата и время с учетом временной зоны (UTC)
    """
    now = dt_in_tz()

    if date is None:
        date = (now.year, now.month, now.day)

    if len(time) < 3:
        time = time + (0,) * (3 - len(time))  # (14, 0, 0)

    eta = datetime(*date, *time, tzinfo=None)
    eta = eta.astimezone(get_tz())

    if eta < now:
        tm = now + timedelta(days=1)  # tomorrow
        eta = eta.replace(day=tm.day, month=tm.month, year=tm.year)

    return eta


def get_worker_config(*queue_names) -> dict:
    return dict(
        # имя исполнителя (для управления)
        hostname=f"{','.join(queue_names)}@{CELERY_APP_NAME}",
        # ...setup_defaults(concurrency, loglevel, logfile, task_events,
        # consumer_cls, autoscaler_cls, pool_putlocks, pool_restarts,
        # optimization или O,  # O maps to -O=fair
        # timer_cls, timer_precision, task_time_limit или time_limit,
        # task_soft_time_limit или soft_time_limit,
        # pool_cls или pool, state_db или statedb,
        # scheduler_cls или scheduler,  # XXX - use [limit / cls / db]
        # schedule_filename, max_tasks_per_child, prefetch_multiplier,
        # disable_rate_limits, worker_lost_wait,
        # max_memory_per_child, **kwargs):
        loglevel='INFO',  # по умолчанию 'WARN'  # logfile = None,
        pool=CELERYD_POOL,
        # наследуется от app, кроме GREEN_POOLS = {'eventlet', 'gevent'}
        # concurrency = CELERYD_CONCURRENCY,  # наследуется от app
        # prefetch_multiplier = 4,  # * worker.concurrency, 0-беск., 4-по-умолч.
        # optimization = 'fair',  # отключает резервирование задач ~ быстрее!
        # task_time_limit = CELERYD_TASK_TIME_LIMIT,  # наследуется от app
        # task_soft_time_limit = CELERYD_TASK_SOFT_TIME_LIMIT,  # наследуется
        # ...setup_instance(queues, ready_callback, pidfile,
        #     include, use_eventloop, exclude_queues, **kwargs):
        queues=queue_names,  # список (Mapping) обрабатываемых очередей
        # убить процесс в linux: kill $(cat /path/to/worker.pid)
        # pidfile = f"{'_'.join(queue_names)}_worker.pid",  # abspath()
        # include = ["tasks"]  # доп. модули с задачами для исп., НЕТ в [tasks]?
    )


def start_worker_cmd(queue_names: str = 'default'):
    """
    publisher: message >> exchange >> queue(s) >> consumer: ack >> del message
    """
    worker_options = [
        ('hostname', f'{queue_names}@{my_app.main}'),
        # наименование исполнителя
        ('loglevel', 'INFO'),  # уровень логирования исполнителя
        ('queues', queue_names),
        # список обрабатываемых исполнителем очередей через запятую
        # ('include', 'tasks'),  # модули с задачами для данного исполнителя
        ('concurrency', 1),  # количество обрабатывающих очереди процессов
        ('pool', 'prefork'),
        # prefork - проц. задачи
        # eventlet - задачи ввода/вывода
        # solo - блокирующий пул
        # не синхронизировать с другими исполнителями при запуске?
        '--without-mingle',
        # не подписываться на события других исполнителей? (missing heart beat)
        # '--without-gossip',
        # '--task-events',  # отправлять события задач мониторящим приложениям?
        # '-O fair'  # оптимизация выполнения задачи, по умолчанию default
    ]

    worker_options = [f'--{opt[0]}={opt[1]}' if isinstance(opt, tuple) else opt
        for opt in worker_options]
    my_app.worker_main(['worker', *worker_options])
    # или app.start(argv = ['celery', 'worker', *worker_options])


def get_registered_tasks():
    # _ = current_app.loader.import_default_modules()
    # tasks = current_app.tasks.keys()
    tasks = list(
        sorted(name for name in my_app.tasks if not name.startswith('celery.')))
    return tasks


def purge_tasks(active_and_reserved=False):
    logger.warning("Выполняется УДАЛЕНИЕ задач Celery...")
    my_app.control.purge()  # remove pending tasks

    if active_and_reserved:  # remove active and reserved tasks
        inspect = my_app.control.inspect()

        active = inspect.active()
        if isinstance(active, dict):
            active = sum(active.values(), [])

        reserved = inspect.reserved()
        if isinstance(reserved, dict):
            reserved = sum(reserved.values(), [])

        jobs = (active or []) + (reserved or [])
        for hostname in jobs:
            tasks = jobs[hostname]
            for task in tasks:
                my_app.control.revoke(task['id'], terminate=True)


if __name__ == '__main__':

    purge_tasks(False)

    # app.start()  # все параметры исполнителя по умолчанию
    # argv=['celery', 'worker', '-A', 'tasks', '-P', 'eventlet', '-l', 'INFO'])

    # start_worker_cmd('default,gost')

    config = get_worker_config(CELERY_TASK_DEFAULT_QUEUE)

    from mongoengine_connections import register_mongoengine_connections

    register_mongoengine_connections(secondary_prefered=True)

    worker: Worker = my_app.Worker(**config)
    worker.start()
