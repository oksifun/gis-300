from datetime import datetime, timedelta

from mongoengine import StringField, Q

from processing.models.choices import WorkerStatus, WorkerQueue
from processing.models.health import Health
from .base import Task, TaskStatus, RequestTask


class RestartErrorsTask(Task):
    meta = {
        "db_alias": "queue-db"
    }

    queue = StringField(verbose_name="Идентификатор очереди", required=True, default=WorkerQueue.MAINTENANCE)

    def process(self, *args, **kwargs):
        self.status = TaskStatus.WORK_IN_PROGRESS
        self.started = datetime.now()
        self.save()

        lock = Health.objects(status=WorkerStatus.OK).count()

        if not lock:
            without_parent = Q(parent__exists=False) | Q(parent=None)
            bad = Q(worker_pid__exists=True) | Q(status=TaskStatus.ERROR)
            bad_parents = Task.objects(without_parent & bad).only('id')
            bad_parents_ids = map(lambda x: x.pk, bad_parents)

            # Убиваем все подзадачи поломанных задач
            Task.objects(parent__in=bad_parents_ids).delete()

            # Чиним поломанные задачи
            Task.objects(bad).update(worker_pid=None, status=TaskStatus.CREATED)

            self.status = TaskStatus.DONE
            self.ended = datetime.now()
        else:
            self.status = TaskStatus.CREATED
            self.delayed = datetime.now() + timedelta(minutes=1)

        self.save()


class RestartErrorsRequestTask(RequestTask):
    meta = {
        "db_alias": "queue-db"
    }

    queue = StringField(verbose_name="Идентификатор очереди", required=True, default=WorkerQueue.MAINTENANCE)

    def process(self, *args, **kwargs):
        self.status = TaskStatus.WORK_IN_PROGRESS
        self.started = datetime.now()
        self.save()

        # сохраняем задачу на освобождение локов с пониженным приоритетом, что позволит
        # разобрать все задачи которые стоят в очереди и только потом убрать локи с подвисших
        RestartErrorsTask(priority=1).save()

        self.status = TaskStatus.DONE
        self.ended = datetime.now()

        self.save()
