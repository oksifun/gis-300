from celery import Celery

from processing.celery.config import CELERY_CONFIG

_QUEUE = 'messages'
MESSAGES_SCHEDULE = {}
MESSAGES_TASK_ROUTES = {
    'app.messages.tasks.users_tasks.update_users_journals': {
        'queue': _QUEUE
    },
    'app.messages.tasks.users_tasks.update_users_tickets': {
        'queue': _QUEUE
    },
    'app.messages.tasks.users_tasks.update_users_news': {
        'queue': _QUEUE
    },
    'app.messages.tasks.users_tasks.import_finished': {
        'queue': _QUEUE
    },
    'app.messages.tasks.users_tasks.update_meters_messages': {
        'queue': _QUEUE
    },
    'app.messages.tasks.mail_groups.regular_mail': {
        'queue': 'regular_mail'
    },
    'app.messages.tasks.mail_groups.access_mail': {
        'queue': 'access_mail'
    },
    'app.messages.tasks.mail_groups.ticket_mail': {
        'queue': 'ticket_mail'
    },
    'app.messages.tasks.mail_groups.rare_mail': {
        'queue': 'rare_mail'
    },
}

ventriloquist = Celery(
    include=[
        'app.messages.tasks',
    ]
)


try:
    from django.conf import settings

    ventriloquist.autodiscover_tasks(settings.INSTALLED_APPS)
except ImportError:
    pass


ventriloquist.conf.update(**CELERY_CONFIG)
ventriloquist.conf.task_routes = {
    **MESSAGES_TASK_ROUTES,
}
