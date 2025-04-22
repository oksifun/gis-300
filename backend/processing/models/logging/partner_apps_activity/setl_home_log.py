import datetime

from mongoengine import Document, DateTimeField, ObjectIdField, StringField, \
    FloatField, IntField


class PartnerBaseActivity(Document):
    """
    Наследуемый класс общей модели коллекции для логов по запросам от партнеров
    """

    meta = {
        'abstract': True,
        'db_alias': 'logs-db',
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
    headers = StringField()
    query_string = StringField()
    user_agent = StringField()

    user = ObjectIdField(verbose_name='ID пользователя')
    role = StringField(verbose_name='Принадлежность пользователя партнеру')
    session = StringField()
    action = StringField()

    result_status = IntField()
    result_len = IntField()
    result_content = StringField()
    millis = FloatField()

    traceback = StringField()


class PartnerAppsGetTokenActivity(PartnerBaseActivity):
    """
    Коллекция логов запросов по получению от пользователей партнеров
    токенов при авторизации
    """

    meta = {
        'collection': 'partner_apps_token_activity',
    }


class SetlHomeActivity(PartnerBaseActivity):
    """
    Коллекция логов запрос от Setl Home
    """

    meta = {
        'collection': 'setl_home_activity',
    }


class MauticActivity(PartnerBaseActivity):
    """
    Коллекция логов запрос от Mautic
    """

    meta = {
        'collection': 'mautic_activity',
    }
