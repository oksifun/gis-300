
from mongoengine import Document, StringField, ObjectIdField

IMPORT_TASK_STATUSES = ('new', 'run', 'ready', 'error',)


class ImportAreaMeterFile(Document):
    meta = {
        'db_alias': 'queue-db',
        'collection': 'ImportAreaMeterFile',
    }

    status = StringField(
        verbose_name='Текущий статус',
        choices=IMPORT_TASK_STATUSES,
        required=True,
        default='new',
    )
    file = ObjectIdField()
