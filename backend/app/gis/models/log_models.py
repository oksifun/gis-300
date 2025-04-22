import datetime

from mongoengine import Document, DateTimeField, StringField


class GisInErrorsLog(Document):
    meta = {
        'db_alias': 'logs-db',
        'collection': 'gis_errors_in',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            '-created',
        ],
    }
    created = DateTimeField(default=datetime.datetime.now)
    message = StringField()
