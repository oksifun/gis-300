# -*- coding: utf-8 -*-  # необходимо для python2.7 и для работы  с asterisk
import os
import sys
import logging
import yaml
from bson import ObjectId

RELEASE = "0.3.2.14"

CHIEF_PYTHON_PATH = '/usr/local/bin/python'

PROCESSES = 0
DEVELOPMENT = False
TORNADO_DEBUG = False
FISCALIZATION_SCHEDULE = True
SBER_SCHEDULE = True
ACCOUNTING_SCHEDULE = True
REGISTRIES_SCHEDULE = True
AUTOPAY_SCHEDULE = True
TELEPHONY_SCHEDULE = True
SEND_EVENTS_NOTIFICATIONS = True
ROSREESTR_SHEDULE = True
SEND_SETL_HOME = True

# предотвращает предупреждение об отсутствии атрибута
DATABASES = dict()
BANK_PROCESSING = dict()

DEFAULT_PROTOCOL = 'https'
DEFAULT_URL = 'lk.eis24.me'
DEFAULT_CABINET_URL_NO_CYR = 'xn----7sbdqbfldlsq5dd8p.xn--p1ai'
DEFAULT_CABINET_URL = 'кабинет-жителя.рф'
BASE_URI = '/api/v2'
DEFAULT_PAY_RETURN_URL = '/#/news/newsList'
DEFAULT_LOCALE = 'ru_RU.UTF-8'

login_url = '/static/login/'
template_path = 'views'

# максимальное число попыток активации пользователя
ACTIVATION_TRIES_MAX = 10
SESSION_EXPIRE_DAYS = 180

MAX_LIMIT = 150

# 456 Ошибки биллинга(процессинга)
LOG_STATUS_CODES = [500, 403, 401, 400, 456]

PERMISSIONS_CACHE = '4h'
SERVICE_BIND_CACHE = '4h'
SESSION_ACTOR_CACHE = '5s'
PROVIDER_BANK_CACHE = '15m'

IP_SUPERS = ['91.122.15.58']

REFINANCING_RATE = 0.0825  # ставка рефинансирования

MAIL_HEADERS = {}

MAIL_SUBJECTS = {
    'REGISTRATION': 'Регистрация личного кабинета',
    'PASSWORD': 'Пароль входа в личный кабинет'
}

ZAO_OTDEL_PROVIDER_OBJECT_ID = ObjectId("526234b0e0e34c4743821ab4")
EIS24_PROVIDER_OBJECT_ID = ObjectId("565c1863ee6538001e491408")
KOTOLUP_PROVIDER_OBJECT_ID = ObjectId("5dfa1cb874b8a10012918e2b")
SEMENCOVA_PROVIDER_OBJECT_ID = ObjectId("62a1e36bdf05df00193eb487")

REGISTRY_EMAIL_SETTINGS = {  # настройки для импорта реестров
    'HOST': 'zrs01.eis24.me',
    'LOGIN': 'reestr@eis24.me',
    'PORT': 7143,
    'PWD': '7SZvgr78s0',
    'PERIOD_MINUTES': 5,
    'PERMITTED_ADDRESSES': ['ssvnec@gmail.com', 'sberbank@s-c300.com'],
    # кол-во писем которые забираем с сервера и которые помечаем при падении
    'MAIL_COUNT': 50,
}
SBER_REGISTRY_SEND_LIMIT = 20
SBER_REGISTRY_GET_LIMIT = 20

GIS_CELERY_REDIS_DB = 3
GIS_BROKER_URL = 'redis://gis_redis:6379'
S300_CELERY_REDIS_DB = 1
S300_BROKER_URL = 'redis://redis:6379'
CELERY_SOFT_TIME_MODIFIER = 1

SEND_MAIL_INSTANTLY = False
IMPORT_TASK_STATUS_EMAILS = [
    'ssv@eis24.me',
    'k.vv@eis24.me',
    'kta@eis24.me',
    'gdo@eis24.me',
    'support@eis24.me',
    'sap@eis24.me',
    'sap@roscluster.ru',
]
SUPPORT_MAIL = 'support@eis24.me'
TGK1_REGISTRY_MAIL = 'gdo@eis24.me'
WARNINGS_MAIL = 'gdo@eis24.me'
TEST_MAIL = ['gdo@eis24.me', 'drs@eis24.me']
REGISTRY_MANAGER_MAIL = 'reestrmanager@eis24.me'
CRITICAL_SITUATIONS_MAIL = [
    'gdo@eis24.me',
    'ssv@eis24.me',
    'developers@eis24.me',
]
CLIENT_MONITORING_WARNING_MAIL = [
    'gdo@eis24.me',
    'ssv@eis24.me',
]
GLOBAL_STATISTICS_MAIL = [
    'gdo@roscluster.ru',
    'ssv@roscluster.ru',
]

# Максимально допустимое отклонение (в метрах) координат при получении
# погоды из кэша (например, 10000)
FORECAST_IO_API_KEY = '4932478838fa5c3aea45800f37cb6f03'
WEATHER_MAX_DISTANCE_METERS = 10000

# seconds
MONITORING_MIN_REQUEST_TIME = 3

DEFAULT_TMP_DIR = '/tmp'

POSSIBLE_EXTENSION_REGISTRY = [
    '.txt',
    '.csv',
    '.xml',
    '.xls',
    'xlsx',
    '.y24'
]

# Джанго
SENTRY_DJANGO = (
    'http://05becf007c874793b807e9b8cecac8fa:4da2ba2a7b624b7da317c1ed0dee9450'
    '@sentry.eis24.me:8080/2'
)
# Сельдерей
SENTRY_CELERY = (
    'http://485e442f1daf420e9837c405c7aede2b:927936ed34994b37a2caf6ca7db58ece'
    '@sentry.eis24.me:8080/5'
)
# Торнадо
SENTRY_WEB_SERVER = (
    'http://0256ae86116c463eb8e1d9637617c6a8:2f7df8481eb94e3389aa5f1e2e04ee8c'
    '@sentry.eis24.me:8080/6'
)
# Процессинг
SENTRY_WORKERS = SENTRY_PROCESSING = SENTRY_API = (
    'http://772ffa71d7b2475ba63379183a8b7622:bc66219a3a314447b9ea0fafd1f94634'
    '@sentry.eis24.me:8080/7'
)

GPRS_TASK_CONTROL_SETTINGS = {
  'max_tries': 3,
  'time_period': 300,
  'manual_actual_time': 60 * 30,  # критерий актульности ручной задачи
  'auto_actual_time': 60 * 60 * 24,  # критерий актульности автом. задачи
}

# Номер симки в шлюзе AMI Yeastar "Астерикса и Обеликса"
# Эти пакеты какая-то ерунда
OBELIX_GATEWAYS = {
    2: dict(
        operator='tele2',
        balance_ussd='*105*1#',
        packet='*155*0#',
        what_a_number='*201#'
    ),
    3: dict(
        operator='mts',
        balance_ussd='*100#',
        packet='*100*1#',
        what_a_number='*111*0887#'
    ),
    4: dict(
        operator='beeline',
        balance_ussd='*102#',
        packet='',
        what_a_number='*110*10#'
    ),
    5: dict(
        operator='megafon',
        balance_ussd='*100#',
        packet='*558#',
        what_a_number='*205#'
    )
}
QR_CALL_URL = 'only_prod'
CREATE_CALL_URL = 'only_prod'

DREAMKAS_DEBUG_TOKEN = '196a095e-791d-4879-a072-e1e30963a311'
DREAMKAS_DEBUG_DEVICE = '10206'

GOV_ACCOUNT = {
    'login': 'gdo@roscluster.ru',
    'password': 'gdo@roscluster.ruQ1',
    # получен на https://data.gov.ru/get-api-key
    'token': 'f0fb03684461bb8c248dfbaeb67bd7e0',
    'csv_file': 'data-20191112T1252-structure-20191112T1247.csv',
    'encoding': 'UTF-8'
}
TELEGRAM_TOKEN = '799681575:AAE9sWzrfkGFogC0TMUEckB0_pDFR9YR6Mw'
TELEGRAM_BOT = dict()  # загружаются из yaml
# ID чатов, указанные вручную
CHAT_IDS = [
    '-313827864'
]

TEST_BILLING_PASSWORD = 'TIFrBDnPBM'

ROOT_DIR: str = os.path.dirname(os.path.abspath(__file__))  # backend
APP_DIR: str = os.path.join(ROOT_DIR, 'app')  # backend/app

GIS = dict()  # загружаются из yaml
ROSREESTR_OPEN_DATA = {
    'username': "undefined",
    'password': "undefined",
}

KAFKA_CONNECTION_URL = ""

MAUTIC = dict()

SETL_HOME = {
    'enabled': False,
    'identificator': 'c300',
    'code': '6a7C5tUl',
    'url': 'https://setlhome.setlhome.ru:8081',
}


def get(name, default=None):
    return globals().get(name, default)


class ImproperlyConfigured(Exception):
    pass


logger = logging.getLogger('c300')

config_file = os.getenv('SETTINGS_FILE')
if config_file is None:
    raise ImproperlyConfigured('No settings file')
logger.warning('Using settings file %s', str(config_file))
with open(config_file) as f:
    attrs = yaml.load(f.read(), Loader=yaml.FullLoader)

this_module = sys.modules[__name__]
for attr_name, attr_value in attrs.items():
    # атрибуты ЗАМЕНЯЮТСЯ одноименными записями в yaml!
    setattr(this_module, attr_name, attr_value)


if not get('USE_SENTRY', False):
    SENTRY_WORKERS = SENTRY_WEB_SERVER = SENTRY_PROCESSING = SENTRY_API \
        = SENTRY_DJANGO = SENTRY_CELERY = 'http://1:1@localhost:12000/123'

