from mongoengine import Document, ObjectIdField, StringField, ListField, \
    BooleanField


class SystemMessage(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'SystemMessage'
    }
    _type = ListField(StringField())

    #  ServiceBindsChangedMessage
    providers = ListField(ObjectIdField())
    house = ObjectIdField()

    # ModelChangedMessage
    permissions_changed = BooleanField()
    model_type = StringField()
    model_id = ObjectIdField()
