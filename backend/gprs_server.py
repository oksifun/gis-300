import logging.config

from gprs.main import GprsAdapterServerApplication
from loggingconfig import GPRS_DICT_CONFIG
from mongoengine_connections import register_mongoengine_connections

if __name__ == '__main__':
    register_mongoengine_connections()
    logging.config.dictConfig(GPRS_DICT_CONFIG)

    handler = logging.FileHandler('gprs_log.log')
    app_log = logging.getLogger("tornado.application")
    app_log.addHandler(handler)
    app_log.setLevel(logging.INFO)

    app_log.info('Инициализация GPRS-сервера')
    app = GprsAdapterServerApplication()

    app_log.info('Запуск GPRS-сервера')
    app.run()
