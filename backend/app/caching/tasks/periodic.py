import datetime

from dateutil.relativedelta import relativedelta
from mongoengine import Document

from app.c300.models.choices import BaseTaskState
from app.caching.models.denormalization import DenormalizationTask
from app.caching.tasks.cache_update import total_seconds
import app.caching.tasks.denormalization as funcs_module
from app.celery_admin.workers.config import celery_app


@celery_app.task(
    bind=True,
    rate_limit="100/m",
    max_retries=3,
    soft_time_limit=total_seconds(seconds=60),
)
def restart_denormalize_tasks(self):
    # импортирует все сабклассы Document с денормализацией
    from processing.models.denormalizing_schema import DENORMALIZING_SCHEMA
    models = {model.__name__: model for model in Document.__subclasses__()}
    tasks = DenormalizationTask.objects(
        state=BaseTaskState.NEW,
        created__lt=datetime.datetime.now() - relativedelta(minutes=5),
    )
    new_tasks = tasks.count()
    for task in tasks:
        _restart_task(task, models)
    tasks = DenormalizationTask.objects(
        state=BaseTaskState.WIP,
        time_limit__lt=datetime.datetime.now() - relativedelta(minutes=5),
        tries__lt=10,
    )
    wip_tasks = tasks.count()
    for task in tasks:
        _restart_task(task, models)
    return f'new {new_tasks}, wip {wip_tasks}'


def _restart_task(task, models):
    if task.func_name:
        func = getattr(funcs_module, task.func_name)
        if func:
            func(
                task_id=task.id,
                **task.kwargs,
            )
        else:
            DenormalizationTask.set_fail_state(task.id)
    elif task.model_name in models:
        funcs_module.foreign_denormalize_data(
            model_from=models[task.model_name],
            field_name=task.field_name,
            object_id=task.obj_id,
            task_id=task.id,
        )
    else:
        DenormalizationTask.set_fail_state(task.id)
