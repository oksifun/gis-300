import datetime

from mongoengine import Document, DateTimeField, ObjectIdField, StringField


class AuthWarning(Document):
    meta = {
        'db_alias': 'logs-db',
        'collection': 'user_auth_warnings',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'user',
        ],
    }

    created = DateTimeField(
        required=True,
        default=datetime.datetime.now,
        verbose_name='Дата создания записи',
    )
    user = ObjectIdField()
    message = StringField()
    deprecated = DateTimeField()
