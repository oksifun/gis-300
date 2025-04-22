import datetime

from dateutil.relativedelta import relativedelta
from mongoengine import ObjectIdField, DateTimeField, StringField, IntField

from app.c300.models.choices import BASE_TASK_STATES_CHOICES, BaseTaskState


class BaseTaskMixin:
    created = DateTimeField(
        verbose_name="Дата создания",
        default=datetime.datetime.now,
    )
    time_limit = DateTimeField(
        verbose_name="Дата лимита по времени выполнения",
    )
    state = StringField(
        choices=BASE_TASK_STATES_CHOICES,
        default=BaseTaskState.NEW,
    )
    finished = DateTimeField(
        verbose_name="Дата окончания",
    )
    author = ObjectIdField(verbose_name='Автор задачи')
    tries = IntField(default=0, verbose_name='Кол-во попыток')

    @classmethod
    def set_state(cls, task_id, state):
        cls.objects(pk=task_id).update(state=state)

    @classmethod
    def set_wip_state(cls, task_id, time_limit_secs=None):
        if not time_limit_secs:
            time_limit_secs = 30 * 60
        cls.objects(
            pk=task_id,
        ).update(
            state=BaseTaskState.WIP,
            time_limit=(
                    datetime.datetime.now()
                    + relativedelta(seconds=time_limit_secs)
            ),
            inc__tries=1,
        )

    @classmethod
    def set_fail_state(cls, task_id):
        cls.set_state(task_id, BaseTaskState.ERROR)

    @classmethod
    def set_success_state(cls, task_id):
        cls.set_state(task_id, BaseTaskState.SUCCESS)


class BaseLogMixin:
    created = DateTimeField(
        verbose_name="Дата создания",
        default=datetime.datetime.now,
    )
    message = StringField(verbose_name="Текст")
