import datetime

from mongoengine import Document, DateTimeField, StringField, ObjectIdField, \
    IntField

from app.admin.models.choices import LOCAL_BASES_CHOICES, \
    DATA_RESTORE_DATA_TYPES_CHOICES, DATA_RESTORE_TASK_STATES_CHOICES, \
    DataRestoreTaskState
from app.c300.models.tasks import BaseTaskMixin, BaseLogMixin


class DataBaseRestoreTask(BaseTaskMixin, Document):
    meta = {
        'db_alias': 'queue-db',
        'collection': 'restore_tasks',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('object_id', '-created'),
            ('author', '-created'),
        ],
    }
    state = StringField(
        choices=DATA_RESTORE_TASK_STATES_CHOICES,
        default=DataRestoreTaskState.NEW,
    )

    data_type = StringField(
        choices=DATA_RESTORE_DATA_TYPES_CHOICES,
        verbode_name="Тип данных для скачивания",
    )
    object_id = StringField(verbose_name="Идентификатор объекта скачивания")
    base_name = StringField(
        choices=LOCAL_BASES_CHOICES,
        verbose_name='База данных, в которую скачать',
    )
    parts_left = IntField(
        verbose_name="Сколько частей осталось незавершёнными, "
                     "если разбито на части",
    )


class DataBaseRestoreLog(BaseLogMixin, Document):
    meta = {
        'db_alias': 'logs-db',
        'collection': 'restore_tasks',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('task', '-created'),
        ],
    }
    task = ObjectIdField(verbode_name='Задача DataBaseRestoreTask')
