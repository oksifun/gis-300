from datetime import datetime

from mongoengine import Document, DateTimeField, StringField, ListField, \
    ObjectIdField, DictField


class FormTwentyTwo(Document):
    meta = {
        "db_alias": "queue-db",
        'collection': 'FormTwentyTwo',
    }
    celery_task = StringField(
        verbose_name="id задачи в celery"
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
        default=['Подготовка к построению отчета'],
        verbose_name="Ход работы"
    )
    created = DateTimeField(
        default=datetime.now,
        verbose_name='Дата создания'
    )
    file = ObjectIdField(
        verbose_name='id файла'
    )
    provider = ObjectIdField(required=False)
    service_types = DictField()
