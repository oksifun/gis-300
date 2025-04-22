from app.gis.workers.config import gis_celery_app
from mongoengine_connections import register_mongoengine_connections
from celery.signals import setup_logging

try:
    from django.conf import settings as django_settings

    gis_celery_app.autodiscover_tasks(django_settings.INSTALLED_APPS)
except ImportError:
    pass


@setup_logging.connect
def _setup_logging(loglevel, logfile, format, colorize, **kwargs):
    import logging.config
    from loggingconfig import DICT_CONFIG
    logging.config.dictConfig(DICT_CONFIG)


@gis_celery_app.on_after_configure.connect
def register_mongo_connections(sender, **kwargs):
    register_mongoengine_connections()


if __name__ == '__main__':
    gis_celery_app.start()
