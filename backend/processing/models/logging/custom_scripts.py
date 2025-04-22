import datetime

from mongoengine import Document, DateTimeField, ObjectIdField, ListField, \
    DictField, StringField


class CustomScriptData(Document):
    """
    Данные, которые меняет скрипт перед изменением
    """

    meta = {
        'db_alias': 'logs-db',
        'collection': 'custom_script_data',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'task',
        ],
    }

    created = DateTimeField(required=True, verbose_name='Дата создания записи')
    task = ObjectIdField(verbose_name='Ссылка на задачу')
    coll = StringField(required=True, verbose_name='Имя коллекции')
    data = ListField(
        DictField(),
        verbose_name='Изменяемые данные',
    )

    def save(self, *args, **kwargs):
        if not self.created:
            self.created = datetime.datetime.now()
        return super().save(*args, **kwargs)
