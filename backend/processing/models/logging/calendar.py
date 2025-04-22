from datetime import datetime

from mongoengine import Document, ListField, DateTimeField, StringField, \
    IntField


class CalendarDownloadingLog(Document):
    """ Лог скачки и парсинга календаря на указанный год """

    meta = {
        'db_alias': 'logs-db',
        'collection': 'CalendarDownloadingLog',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'year'
        ]
    }
    year = IntField(verbose_name='Год календаря')
    log = ListField()
    state = StringField(choices=('wip', 'ready', 'failed'))
    created = DateTimeField(default=datetime.now)
    updated = DateTimeField()

    def save(self, *args, **kwargs):
        self.updated = datetime.now()
        super().save(*args, **kwargs)
