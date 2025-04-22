import datetime

from mongoengine import StringField, Document, DictField, DateTimeField, \
    ObjectIdField


class DeletedData(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'deleted_data',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('ins_id', 'model'),
        ],
    }

    model = StringField()
    ins_id = ObjectIdField()
    data = DictField()
    created = DateTimeField(default=datetime.datetime.now)
