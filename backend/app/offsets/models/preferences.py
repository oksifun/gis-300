import datetime

from mongoengine import Document, ObjectIdField, DateTimeField, IntField, \
    ListField


class ServiceSplitRestrictedProviders(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'service_split_restricted_providers',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('provider', 'closed'),
        ],
    }

    provider = ObjectIdField(verbose_name='Организация')
    created = DateTimeField(
        default=datetime.datetime.now,
        verbose_name='Создано',
    )
    closed = DateTimeField(verbose_name='Отменено')


class UpdateOffsetsProviders(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'update_offsets_providers',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('provider', 'closed', 'version'),
        ],
    }

    provider = ObjectIdField(verbose_name='Организация')
    created = DateTimeField(
        default=datetime.datetime.now,
        verbose_name='Создано',
    )
    closed = DateTimeField(verbose_name='Отменено')
    version = IntField(verbose_name='Какой версией обновлено')
    # жители-исключения
    accounts_exclude = ListField(ObjectIdField())
