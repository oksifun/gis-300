import datetime

from mongoengine import Document, ObjectIdField, DateTimeField, IntField


class UpdateSberRegistryProviders(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'update_sber_registry_providers',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('provider', 'version', 'closed'),
        ],
    }

    provider = ObjectIdField(verbose_name='Организация')
    created = DateTimeField(
        verbose_name='Создано',
        default=datetime.datetime.now,
    )
    closed = DateTimeField(verbose_name='Отменено')
    version = IntField(verbose_name='Версия блокированного реестра')
