import datetime

from mongoengine import Document, DateTimeField, ObjectIdField, StringField


class AcquiringErrorLog(Document):
    """
    Модель лога неудачной попытки оплаты платежа
    """
    meta = {
        "db_alias": "logs-db",
        'collection': 'providers_errors',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('provider', 'date'),
            ('tenant', 'date'),
        ],
    }

    provider = ObjectIdField(verbose_name="Организация, выставившая платеж")
    date = DateTimeField(
        verbose_name="Дата попытки оплаты",
        default=datetime.datetime.now,
    )
    error_message = StringField(verbose_name="Сообщение об ошибке")
    tenant = ObjectIdField(verbose_name="Житель")
    accrual = ObjectIdField(verbose_name="Платеж")
    template = ObjectIdField(verbose_name="Шаблон, в котором произошла ошибка")
