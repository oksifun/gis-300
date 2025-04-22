from mongoengine import Document, DateTimeField, ObjectIdField, ListField, \
    StringField, DynamicField, IntField


class PipcaLog(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'PipcaLog',
    }

    log_type = ListField(StringField(), db_field='_type')
    author = ObjectIdField()
    datetime = DateTimeField()
    doc = ObjectIdField()
    tenants = ListField(ObjectIdField())
    descriptions = ListField(StringField())
    measured_data = DynamicField()
    action = StringField()
    service_type = ObjectIdField()
    seconds = IntField()
    service_name = StringField()
    formula = StringField()

