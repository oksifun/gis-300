from mongoengine import Document, ObjectIdField, DateTimeField


class FakeGisTask(Document):
    meta = {
        'db_alias': 'queue-db',
        'collection': 'fake_gis',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'doc',
        ],
    }
    doc = ObjectIdField(verbose_name='Документ AccrualDoc')
    created = DateTimeField()
    finished = DateTimeField()
