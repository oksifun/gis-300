from celery import Celery
from processing.celery.config import CELERY_CONFIG


_QUEUE = 'permissions'
PERMISSIONS_TASK_ROUTES = {
    'app.permissions.tasks.binds_permissions.process_house_binds_models': {
        'queue': _QUEUE,
    },
    'app.permissions.tasks.binds_permissions.process_house_binds': {
        'queue': _QUEUE,
    },
    'app.permissions.tasks.binds_permissions.process_provider_binds_models': {
        'queue': _QUEUE,
    },
    'app.permissions.tasks.binds_permissions.process_provider_binds': {
        'queue': _QUEUE,
    },
    'app.permissions.tasks.binds_permissions.process_department_binds_models': {
        'queue': _QUEUE,
    },
    'app.permissions.tasks.binds_permissions.process_department_binds': {
        'queue': _QUEUE,
    },
    'app.permissions.tasks.binds_permissions.process_account_binds_models': {
        'queue': _QUEUE,
    },
    'app.permissions.tasks.binds_permissions.process_account_binds': {
        'queue': _QUEUE,
    },
    'app.permissions.tasks.binds_permissions.sync_permissions': {
        'queue': _QUEUE,
    },
}

joker_app = Celery(
    include=[
        'app.permissions.tasks.binds_permissions',
    ]
)


try:
    from django.conf import settings

    joker_app.autodiscover_tasks(settings.INSTALLED_APPS)
except ImportError:
    pass


joker_app.conf.update(**CELERY_CONFIG)
joker_app.conf.beat_schedule = {}
joker_app.conf.task_routes = {
    **PERMISSIONS_TASK_ROUTES,
}
