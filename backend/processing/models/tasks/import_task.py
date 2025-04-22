import datetime

from mongoengine import Document, DynamicField, StringField, ObjectIdField, \
    DateTimeField, ListField, DictField

IMPORT_TASK_STATUSES = ('new', 'ready', 'error', 'finished', 'accepted', 'run')


class ImportTask(Document):
    """
    Задачи по импорту данных
    Модель устарела и не должна подвергаться изменениям, т.к. импорт должен
    быть переделан, а модель удалена
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'ImportTask',
    }

    files = DynamicField()
    status = StringField()
    created_by = ObjectIdField()
    created_at = DateTimeField()


class CustomScriptRunTask(Document):
    meta = {
        'db_alias': 'queue-db',
        'collection': 'custom_script_run_tasks',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'status',
        ],
    }

    # обязательные исходные данные
    created = DateTimeField(verbose_name='Создано', required=True)
    updated = DateTimeField(verbose_name='Изменено', required=True)
    status = StringField(
        verbose_name='Текущий статус',
        choices=IMPORT_TASK_STATUSES,
        required=True,
        default='new',
    )
    author_id = ObjectIdField(
        required=True,
        verbose_name='Автор задачи - сотрудник',
    )
    provider = ObjectIdField(
        required=True,
        verbose_name='Организация, для которой выполняется скрипт',
    )
    accepted_by = ObjectIdField(verbose_name='Сотрудник, подтвердивший скрипт')
    log = ListField(StringField(), verbose_name='Лог')
    name = StringField(verbose_name='Имя функции скрипта')
    params = DictField(verbose_name='Параметры функции скрипта')

    def save(self, *args, **kwargs):
        if not self.created:
            self.created = datetime.datetime.now()
        self.updated = datetime.datetime.now()
        return super().save(*args, **kwargs)

