import datetime

from mongoengine import Document, StringField, ObjectIdField, BooleanField, \
    DateTimeField


class GisImportStatus(Document):

    meta = {
        'db_alias': 'logs-db',
        'collection': 'gis_import_statuses',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'task',
        ],
    }

    date = DateTimeField(required=True, default=datetime.datetime.now)

    # статус, который возвращает ГИС или наш, хранится в свободной читабельной
    # форме
    status = StringField(required=True, default='')

    task = ObjectIdField(required=True)
    is_error = BooleanField()
    description = StringField()

