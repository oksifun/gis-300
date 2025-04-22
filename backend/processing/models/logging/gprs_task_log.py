import datetime

from mongoengine import Document, StringField, ObjectIdField, DateTimeField, \
    ListField


class GprsTaskLog(Document):
    """Логирование опроса прибора по GPRS"""

    meta = {
        'db_alias': 'logs-db',
        'collection': 'gprs_task_log',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'task',
        ],
    }
    date = DateTimeField(
        verbose_name="Дата создания лога",
        required=True,
        default=datetime.datetime.now
    )
    task = ObjectIdField(required=True, verbose_name="ID задачи")
    actions_history = ListField(StringField())

    def log_msg(self, message):
        """Логирование задачи переданным сообщением"""
        self.actions_history.append(f'{datetime.datetime.now()} {message}')
        self.save()


class GprsConnectionsErrors(Document):
    """Для логирования ошибок на этапе подключения устройства"""

    meta = {
        'db_alias': 'logs-db',
        'collection': 'gprs_connections_errors'
    }
    date = DateTimeField(
        verbose_name="Дата создания лога",
        required=True,
        default=datetime.datetime.now,
    )
    device_address = StringField(verbose_name="Адрес подключения")
    description = StringField(verbose_name="Описание ошибки")
    traceback = StringField(verbose_name="Описание ошибки")
