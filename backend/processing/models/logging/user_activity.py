import datetime

from mongoengine import Document, DateTimeField, ObjectIdField, StringField, \
    FloatField, BooleanField, IntField


class UserActivity(Document):
    """
    Данные, которые меняет скрипт перед изменением
    """

    meta = {
        'db_alias': 'logs-db',
        'collection': 'user_activity',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('user', 'created'),
            ('url', 'created'),
            'created',
        ],
    }

    created = DateTimeField(
        required=True,
        default=datetime.datetime.now,
        verbose_name='Дата создания записи',
    )
    url = StringField(required=True, verbose_name='Урла')
    addr = StringField()
    method = StringField()
    body = StringField()
    query_string = StringField()

    user = ObjectIdField(verbose_name='ID пользователя')
    session = StringField()
    provider = ObjectIdField()
    action = StringField()
    session_ip = StringField()
    superuser = BooleanField()
    slave = ObjectIdField()

    result_status = IntField()
    result_len = IntField()
    result_content = StringField()
    millis = FloatField()

    traceback = StringField()
