from os import name as platform, environ
from pytz import timezone  # НЕ datetime.timezone!

from kombu import Queue  # Exchange, binding

CELERY_TASK_ALWAYS_EAGER = False

UTC_TIMEZONE = timezone('UTC')
LOCAL_TIMEZONE = timezone('Europe/Moscow')

CELERY_ENABLE_UTC = True  # время выпонения задач задается по Гринвичу (+00:00)
CELERY_TIMEZONE = UTC_TIMEZONE if CELERY_ENABLE_UTC else LOCAL_TIMEZONE

CELERY_IMPORTS = []  # импортируемые модули с задачами, обаботчиками событий,...
CELERY_INCLUDE = [  # ВНИМАНИЕ! НЕ ОСТАВЛЯТЬ ЛИШНИХ ЗАПЯТЫХ В КОНЦЕ НАБОРА!
    "processing.celery.workers.riddler.tasks",
    # "processing.soap_integration.gis.tasks",  # можно просто "tasks"
]  # модули с задачами для всех исполнителей (загружаются после imports)

# путь модуля при непосредственном выполнении скрипта
CELERY_APP_NAME = 'processing.soap_integration.gis.tasks'
# задачи регистрируются с именами:
# celery_app.main + task_method.name, например <@task: __main__.add>

CELERYD_HIJACK_ROOT_LOGGER = False  # True - перекрывать все обработчики logging

# RabbitMQ (PyAMQP) - Advanced Message Queuing Protocol
# Redis - Remote Dictionary Service (не AMQP)
BACKEND_URI = "redis://redis:6379/"
BROKER_URL = f"{BACKEND_URI}/0"
# 'memory://localhost/'  # только как брокер
# redis://username:password@hostname:port/db_number
CELERY_RESULT_BACKEND = f"{BACKEND_URI}/1"

# макс. кол-во подключений к боркеру, по умолчанию = 10, None - всегда новое
BROKER_POOL_LIMIT = 4

# время ожидания подтверждения принятия сообщения (Ack) от броекра в сек.
BROKER_VISIBILITY_TIMEOUT = 60 * 60 * 2
# TIMEOUT ДОЛЖЕН БЫТЬ БОЛЬШЕ ETA/COUNTDOWN *ВСЕХ* ВЫПОЛНЯЕМЫХ ЗАДАЧ,
# ИНАЧЕ ОНИ БУДУТ ПОСТАВЛЕНЫ В ОЧЕРЕДЬ МНОГОКРАТНО!

BROKER_TRANSPORT_OPTIONS = {
    'max_retries': 2,
    'interval_start': 0, 'interval_step': 0.2, 'interval_max': 0.5
}  # решение проблемы с бесконечным подключением при упавшем брокере

# solo - блокирующий пул
# prefork - процессор-зависимые задачи
# eventlet - задачи ввода/вывода или gevent  # pip install eventlet или gevent
CELERYD_POOL = 'prefork'  # пул по умолчанию - может быть переопределен исп.

# ВНИМАНИЕ! Redis-backend в Windows работает с (не solo) пулом только при
# FORKED_BY_MULTIPROCESSING = 1
if platform == 'nt':  # ОБЯЗАТЕЛЬНАЯ переменная окружения в Windows!
    environ.setdefault('FORKED_BY_MULTIPROCESSING', '1')

# кол-во процессов исполнителя, по умолчанию - кол-во ядер процессора(ов)
CELERYD_CONCURRENCY = 2
# кол-во зарезервированных исполнителем задач (без обращения к очереди)
CELERYD_PREFETCH_MULTIPLIER = 1

# по умолчанию задачи НЕ ограничены по врмени!  # ТОЛЬКО prefork и gevent!
# время в сек. до завршения выполняющего задачу процесса и создания нового
CELERYD_TASK_TIME_LIMIT = 60 * 5
# вызывает исключение до (hard) завершения процесса  # с Redis НЕ работает!
# в Windows не поддерживается сигнал SIGUSR1!
CELERYD_TASK_SOFT_TIME_LIMIT = 60 * 10 if platform != 'nt' else None

# макс. время пребывания в очереди задач в сек., по умолчанию - 1 день
CELERY_TASK_RESULT_EXPIRES = 60 * 5

# pawelzny.com/python/celery/2017/08/07/must-have-celery-4-configuration/
# pickle, json, yaml, msgpack (experimental)  # сериализатор по умолчанию
DEFAULT_SERIALIZER = 'json'
# JSON-СЕРИАЛИЗАТОР ВСЕГДА ВОЗВРАЩАЕТ РЕЗУЛЬТАТЫ ЗАДАЧИ В ВИДЕ СТРОКИ!
# передача параметров задачи в ASCII-кодировке ведет к ошибке JSON-сериализатора
CELERY_ACCEPT_CONTENT = ['pickle', 'json']  # форматы данных исполнителя
CELERY_TASK_SERIALIZER = 'pickle'  # формат данных для отправки в очередь
CELERY_RESULT_SERIALIZER = 'json'  # формат передачи результа выполнения задачи

# по умолчанию (нет в task и routes) задачами используется очередь "celery"
CELERY_TASK_DEFAULT_QUEUE = 'gis'
CELERY_TASK_DEFAULT_RATE_LIMIT = '1000/m'  # макс. кол-во задач в ед. времени

CELERY_QUEUES = [  # kombu.Queue, Broadcast или Mapping (set, list)
    Queue(CELERY_TASK_DEFAULT_QUEUE),
    # Queue(CELERY_DEFAULT_QUEUE, CELERY_DEFAULT_EXCHANGE,
    #     routing_key = CELERY_DEFAULT_QUEUE),
    # Queue(CELERY_DEFAULT_QUEUE, [binding(Exchange(CELERY_DEFAULT_EXCHANGE),
    #     routing_key = CELERY_DEFAULT_QUEUE)]),
    # Broadcast('broadcast'),
]  # None - автоматически создавать очереди
# 'полный.путь.декорированного.метода':
#     {'queue': 'наименование очереди исполнителя'} или kombu.Queue
# 'наименование метода':
#     {'exchange': 'название exchange', 'routing_key': 'название ключа'},
# звездочка используется для ВСЕХ декорированных методов в указанном модуле!
CELERY_ROUTES = {  # {'delivery_mode': 'transient'}
    # 'processing.soap_integration.gis.tasks.*':
    #     {'queue': CELERY_TASK_DEFAULT_QUEUE},
    f"{module}.*":
        {'queue': CELERY_TASK_DEFAULT_QUEUE}
    for module in CELERY_INCLUDE
}
# CELERY_ROUTES = {'tasks.*': {'queue': CELERY_TASK_DEFAULT_QUEUE}}
# CELERY_ROUTES[f'{CELERY_APP_NAME}.*'] = {'queue': CELERY_TASK_DEFAULT_QUEUE}

# перенаправлять print() от исполнителей в текущий лог, по умолчанию = True
CELERYD_REDIRECT_STDOUTS = False
# уровень логирования для перенаправленных сообщений, по умолчанию = 'WARN'
CELERYD_REDIRECT_STDOUTS_LEVEL = 'INFO'
