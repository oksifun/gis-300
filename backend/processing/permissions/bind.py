from mongoengine import Document, StringField, ObjectIdField


class Bind(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Bind',
    }

    obj = ObjectIdField()
    col = StringField()

