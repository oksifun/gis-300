from mongoengine import Document, ObjectIdField, ReferenceField, StringField, \
    DynamicField, ListField


class ProviderPublicData(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'ProviderPublicData'
    }

    provider = ReferenceField(
        'processing.models.billing.provider.main.Provider', required=True)
    bind = ObjectIdField()
    _type = ListField(StringField())

    data_type = StringField()
    data = DynamicField()

