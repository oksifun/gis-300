from mongoengine import Document, ReferenceField, DateTimeField, ObjectIdField


class AreaBind(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'AreaBind',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'area',
            'provider',
        ],
    }

    area = ObjectIdField()
    provider = ReferenceField('processing.models.billing.provider.Provider',
                              verbose_name='Организация')
    created = DateTimeField()
    closed = DateTimeField()

