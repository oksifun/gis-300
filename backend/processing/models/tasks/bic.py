from datetime import datetime

from mongoengine import Document, DateTimeField, StringField, ListField

from lib.helpfull_tools import DateHelpFulls as dhf


class BikSync(Document):
    meta = {
        "db_alias": "queue-db",
        'collection': 'BikSync',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'date',
        ]
    }

    date = DateTimeField(
        required=True,
        verbose_name="Дата за которую нужно получить файл"
    )
    state = StringField(
        verbose_name="Статус задачи",
        choices=(
            'wip',  # в работе
            'failed',  # провалена
            'ready',  # готова

        ),
        default='wip'
    )
    log = ListField(
        StringField(),
        default=[],
        verbose_name="Ход работы"
    )
    created = DateTimeField(
        default=datetime.now,
        verbose_name='Дата создания'
    )

    def save(self, *args, **kwargs):
        if self.date:
            self.date = dhf.start_of_day(self.date)
        super().save(*args, **kwargs)
