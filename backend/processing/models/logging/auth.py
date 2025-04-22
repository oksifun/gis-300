import datetime

from mongoengine import Document, DateTimeField, ObjectIdField, StringField


class UserActionWarning(Document):
    """
    Данные, которые меняет скрипт перед изменением
    """

    meta = {
        'db_alias': 'logs-db',
        'collection': 'auth_warnings',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('user', 'created'),
            'source',
            'created',
        ],
    }

    created = DateTimeField(
        required=True,
        default=datetime.datetime.now,
        verbose_name='Дата создания записи',
    )
    user = ObjectIdField()
    source = StringField()
    session = StringField()
    provider = ObjectIdField()
    message = StringField()
