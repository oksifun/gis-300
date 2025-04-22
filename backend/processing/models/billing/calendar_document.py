from datetime import datetime

from mongoengine import Document, StringField, DictField, DateTimeField, \
    IntField


class Calendar(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Calendar',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'year',
        ]
    }
    year = IntField(required=True, verbose_name='Год календаря')
    description = StringField(verbose_name='Описание календаря от API')
    map = DictField(verbose_name='Сам календарик')
    created = DateTimeField(default=datetime.now)

    def save(self, *args, **kwargs):
        if isinstance(self.year, datetime):
            self.year = self.year.year
        super().save(*args, **kwargs)
