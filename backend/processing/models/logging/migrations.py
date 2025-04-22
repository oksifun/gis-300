import datetime

from mongoengine import Document, StringField, DateTimeField, \
    ListField, IntField, BooleanField


class MigrationsLog(Document):
    """Логирование миграций исполняемых в Celery"""

    meta = {
        'db_alias': 'logs-db',
        'collection': 'Migrations'
    }
    date = DateTimeField(verbose_name="Дата создания лога")
    state = StringField(choices=('started', 'succeed', 'failed'))
    log = ListField(StringField(), verbose_name="Сообщения по ходу выполнения")
    progress = IntField(default=0, verbose_name="Прогресс выполения задачи в %")
    script_name = StringField(verbose_name="Название логируемого скрипта")
    processed = BooleanField(verbose_name='Обработана ли ошибка')

    def save(self, *args, **kwargs):
        if not self.date:
            self.date = datetime.datetime.now()
        if isinstance(self.progress, float):
            self.progress = round(self.progress)
        super().save(*args, **kwargs)
