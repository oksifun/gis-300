from datetime import timedelta


from celery.signals import setup_logging
from celery import Celery

import settings
from app.accruals.workers.caching.config import ACCRUALS_CACHING_TASK_ROUTES, \
    ACCRUALS_CACHING_TASK_SCHEDULE
from app.accruals.workers.dollmaker.config import DOLLMAKER_TASK_ROUTES
from app.accruals.workers.penguin.config import CALCULATE_ACCRUALS_SCHEDULE, \
    CALCULATE_ACCRUALS_TASK_ROUTES
from app.admin.workers.config import ADMIN_TASK_ROUTES, ADMIN_TASK_SCHEDULE
from app.caching.workers.config import CACHING_TASK_ROUTES, \
    CACHING_TASK_SCHEDULE
from app.clean_db.workers.config import CLEAN_DB_TASK_ROUTES, \
    CLEAN_DB_TASK_SCHEDULE
from app.legal_entity.workers.config import LEGAL_ENTITY_TASK_ROUTES
from app.messages.workers.config import MESSAGES_TASK_ROUTES
from app.offsets.workers.config import OFFSETS_TASK_ROUTES
from app.permissions.workers.config import PERMISSIONS_TASK_ROUTES
from app.public.workers.mosquito.config import QR_CALLS
from app.requests.workers.config import REQUEST_TASK_ROUTES, \
    REQUEST_TASK_SCHEDULE
from mongoengine_connections import register_mongoengine_connections
from processing.celery.config import CELERY_CONFIG
from app.accruals.workers.toyman.config import TOYMAN_TASK_ROUTES
from app.gis.workers.config import (
    GIS_TASK_ROUTES,
    GIS_TASK_SCHEDULE,
)


@setup_logging.connect
def _setup_logging(loglevel, logfile, format, colorize, **kwargs):
    import logging.config
    from loggingconfig import DICT_CONFIG
    logging.config.dictConfig(DICT_CONFIG)


def total_seconds(**kwargs):
    return int(timedelta(**kwargs).total_seconds())


celery_app = Celery(
    include=[
        # define your task modules here
        'app.accruals.tasks.caching',
        'app.admin.tasks.data_restore',
        'app.admin.tasks.statistics',

        'app.accruals.tasks.cache.house_service',
        'app.accruals.tasks.caching',
        'app.accruals.tasks.receipt_tasks',
        'app.accruals.tasks.reports',

        'app.bankstatements.tasks.compare',
        'app.caching.tasks.cache_update',
        'app.caching.tasks.denormalization',
        'app.caching.tasks.compendium_provider_binds',
        'app.caching.tasks.filter_data_prepare',
        'app.caching.tasks.periodic',
        'app.clean_db.tasks.permissions',
        'app.file_storage.tasks.clean_files',

        'app.gis.tasks.bills',
        'app.gis.tasks.house',
        'app.gis.tasks.metering',
        'app.gis.tasks.nsi',
        'app.gis.tasks.org',
        'app.gis.tasks.scheduled',
        'app.gis.tasks.async_operation',

        'app.legal_entity.tasks.update_vendor',
        'app.messages.tasks.mail_groups',
        'app.messages.tasks.users_tasks',
        'app.meters.tasks.import_meter_readings',
        'app.permissions.tasks.binds_permissions',
        'app.requests.tasks.checking_new_applications',
        'app.requests.tasks.linking_request_to_call',

        'app.public.tasks.qr_call',

        'processing.celery.tasks.cleaning_tmp',
        'processing.celery.tasks.periodic_tasks',
        'processing.celery.tasks.sendmail',
    ]
)


try:
    from django.conf import settings as django_settings

    celery_app.autodiscover_tasks(django_settings.INSTALLED_APPS)
except ImportError:
    pass


celery_app.conf.update(**CELERY_CONFIG)
beat_schedule = {
    **CALCULATE_ACCRUALS_SCHEDULE,
    **GIS_TASK_SCHEDULE,
    **CLEAN_DB_TASK_SCHEDULE,
    **CACHING_TASK_SCHEDULE,
    **REQUEST_TASK_SCHEDULE,
    **ADMIN_TASK_SCHEDULE,
    **ACCRUALS_CACHING_TASK_SCHEDULE,
}

celery_app.conf.beat_schedule = beat_schedule
celery_app.conf.task_routes = {
    # sendmail
    'processing.celery.tasks.sendmail.sendmail': {
        'queue': 'access_mail'
    },
    'processing.celery.tasks.sms.send_sms': {
        'queue': 'rare_mail'
    },

    # phonecalls
    'processing.celery.tasks.phonecalls.calldebtor': {
        'queue': 'phonecalls'
    },
    'processing.celery.tasks.phonecalls.schedule_calls': {
        'queue': 'phonecalls'
    },
    'processing.celery.tasks.phonecalls.schedule_tasks': {
        'queue': 'phonecalls'
    },
    'processing.celery.tasks.phonecalls.when_task_finished': {
        'queue': 'phonecalls'
    },
    'processing.celery.tasks.phonecalls.create_calldebtors_tasks': {
        'queue': 'rare_tasks'
    },
    'processing.celery.tasks.phonecalls.create_calldebtors_task': {
        'queue': 'rare_tasks'
    },
    'processing.celery.tasks.phonecalls.send_sms_by_obelix': {
        'queue': 'phonecalls'
    },
    'processing.celery.tasks.phonecalls.check_sim_balances': {
        'queue': 'phonecalls'
    },

    # опрос тепловычислителей
    'processing.celery.tasks.heat_hunter.process_heat_hunter_task': {
        'queue': 'heat_hunter'
    },
    'processing.celery.tasks.heat_hunter.control_gprs_task': {
        'queue': 'heat_hunter'
    },
    'processing.celery.tasks.heat_hunter.freeze_task_cleaner': {
        'queue': 'heat_hunter'
    },
    'processing.celery.tasks.heat_hunter.call_meter': {
        'queue': 'heat_hunter'
    },
    'processing.celery.tasks.heat_hunter.send_tuning_sms': {
        'queue': 'heat_hunter'
    },
    'processing.celery.tasks.heat_hunter.set_periodic_automation_tasks': {
        'queue': 'heat_hunter'
    },
    'processing.celery.tasks.heat_hunter.automation_tasks_starter': {
        'queue': 'heat_hunter'
    },

    'processing.celery.tasks.periodic_tasks.clean_cache': {
        'queue': 'caching'
    },
    'processing.celery.tasks.cleaning_tmp.clean_filters_cash': {
        'queue': 'caching'
    },
    **ACCRUALS_CACHING_TASK_ROUTES,
    **OFFSETS_TASK_ROUTES,
    # права и привязки
    **PERMISSIONS_TASK_ROUTES,
    # кэширование
    **CACHING_TASK_ROUTES,
    # мессенджер
    **MESSAGES_TASK_ROUTES,
    **ACCRUALS_CACHING_TASK_ROUTES,
    # Печать одиночных квитанций
    **TOYMAN_TASK_ROUTES,
    # Массовая печать квитанций
    **DOLLMAKER_TASK_ROUTES,
    # недопоставки
    **CALCULATE_ACCRUALS_TASK_ROUTES,
    # ГИС
    **GIS_TASK_ROUTES,
    **ADMIN_TASK_ROUTES,
    **LEGAL_ENTITY_TASK_ROUTES,
    **CLEAN_DB_TASK_ROUTES,
    **QR_CALLS,
    **REQUEST_TASK_ROUTES,
}


@celery_app.on_after_configure.connect
def register_mongo_connections(sender, **kwargs):
    register_mongoengine_connections()
