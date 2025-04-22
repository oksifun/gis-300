# -*- coding: utf-8 -*-
import os
import sys

import yaml

import settings
from loggingconfig import DICT_CONFIG

LOGGING = DICT_CONFIG

# Разрешим передавать в контроллеры совокупный размер файлов до 250 Мб
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024 * 250

SECRET_KEY = '(p+8a5!@_@p1fb#bf*$sk7562k5u6h&@x%(ubmwg-_tp7*8h_*'
DEBUG = settings.DEVELOPMENT

if DEBUG:
    ALLOWED_HOSTS = ['*']
else:
    ALLOWED_HOSTS = [
        'lk.c300.me',
        'lk.eis24.me',
        'lk.c-300.online',

        'lk.exploitation-gs.ru',
        'lk.tsnr.ru',
        'lk.lumiere-comfort.ru',
        'lk.seatown.ru',
        'lk.pioneer.ru',
        'lk.zanevskiy-komfort.ru',
        'lk.morskoyportal.ru',
        'lk.uk-platinum.ru',
        'lk.uk-harmony.ru',
        'lk.vernissage.life',
        'lk.operation-gs.ru',
        'manager.operation-gs.ru',
        'lk.b-comfort.ru',
        'manager.b-comfort.ru',
        'lk.szrc11.ru',
        'xn--j1ab.xn--j1aafuh.xn--p1ai',
        'lk.kiproko.ru',
        'lk.ukgestor.ru',
        'lk.roscluster.ru',
        '1c.roscluster.ru',

        'hotfix.eis24.me',
        'stage.eis24.me',
        'showroom.eis24.me',

        'xn----7sbdqbfldlsq5dd8p.xn--p1ai'
    ]

RAVEN_CONFIG = {
    'dsn': settings.SENTRY_DJANGO
}

INSTALLED_APPS = [
    'raven.contrib.django.raven_compat',
    'django.contrib.auth',
    'django.contrib.contenttypes',

    'django_prometheus',
    'rest_framework',
    'rest_framework_mongoengine',
    'django_extensions',
    'app.c300',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',

    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'config.urls'

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Europe/Moscow'

USE_I18N = True

USE_L10N = True

USE_TZ = False

STATIC_URL = '/static/'

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'EXCEPTION_HANDLER': 'utils.drf.handlers.custom_exception_handler',
    'PAGE_SIZE': 100,
    'DEFAULT_METADATA_CLASS': 'rest_framework.metadata.SimpleMetadata',
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'utils.drf.authentication.SlaveSessionAuthentication',
        'utils.drf.authentication.MasterSessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'utils.drf.permissions.IsAuthenticated',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'send_bills': '1/minute',
    }
}
# Если включена отладка, то удаляем переопределенный обработчик ошибок
if DEBUG:
    del REST_FRAMEWORK['EXCEPTION_HANDLER']

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.jinja2.Jinja2',
        'DIRS': [
            './views/mail',
            './views/trial_balance',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'environment': 'config.jinja2.environment',
        }
    },
]

config_file = os.getenv('SETTINGS_FILE')
if config_file is None:
    raise settings.ImproperlyConfigured('No settings file')

with open(config_file) as f:
    attrs = yaml.load(f.read(), Loader=yaml.FullLoader)

this_module = sys.modules[__name__]
for attr_name, attr_value in attrs.items():
    setattr(this_module, attr_name, attr_value)
setattr(this_module, 'MONGODB_DATABASES', getattr(this_module, 'DATABASES'))

redis_locations = attrs['CACHES']['default']['LOCATION']
redis_hosts = [tuple(location.split(":")) for location in redis_locations]

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": redis_hosts,
        },
    },
}

CELERY_CHUNK_GROUP_SIZE = 2
