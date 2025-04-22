import datetime

from mongoengine import ObjectIdField, ListField, StringField

from app.messages.models.messenger import UserTasks
from app.accruals.models.tasks import CommonAccrualTask, SubTask, \
    ProviderEmbedded
from processing.models.tasks.choices import TaskStateType


class ReceiptPDFTask(CommonAccrualTask):
    """
    Задача обращения к ReceiptTask - формирование pdf-файлов квитанций.
    """
    meta = {
        'db_alias': 'queue-db',
        'collection': 'receipt_tasks',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'doc',
        ],
    }
    houses = ListField(
        ObjectIdField(),
        verbose_name='Список домов, присутствующих в документах в задаче'
    )
    result_file = ObjectIdField()
    lock_key = StringField()

    @classmethod
    def change_sub_task_state(cls, task_id, task_ix, task_name, state,
                              progress=None):
        timestamp = datetime.datetime.now()
        log_message = \
            f'{timestamp} ' \
            f'ix{task_ix} {task_name} changed to {state}'
        update_query = {
            f'set__tasks__{task_ix}__state': state,
            'push__log': log_message,
            'set__updated': timestamp,
        }
        if progress is not None:
            update_query[f'set__tasks__{task_ix}__progress'] = progress
        cls.objects(
            pk=task_id,
        ).update(
            **update_query,
        )
        cls.change_task_state(task_id, task_name, state)

    @classmethod
    def change_task_state(cls, task_id, task_name, sub_task_state):
        state = None
        update_query = dict()
        task = cls.objects(pk=task_id).get()
        if sub_task_state == 'wip' and task.state == 'new':
            update_query.update({
                'set__started': datetime.datetime.now(),
            })
            state = sub_task_state
        if sub_task_state == 'canceled':
            state = 'canceled'
        if sub_task_state in ('failed', 'finished'):
            if all(map(lambda m: m.state == 'failed', task.tasks)):
                state = 'failed'
            elif all(map(lambda m: m.state in ('finished', 'failed'),
                         task.tasks)):
                state = 'finished'
        progress = int(
            sum((t.progress or 0) for t in task.tasks)
            / len(task.tasks)
        )
        if task.doc:
            UserTasks.send_notices(
                [task.author],
                obj_key='receipts',
                message=state,
                obj_id=task.doc,
                count=progress,
                url=task.url
            )
        if not state:
            return
        update_query.update({
            'set__state': state
        })
        log_message = f'{datetime.datetime.now()} ' \
                      f'{task_name} changed to {state}'
        update_query.update({
            'push__log': log_message,
        })
        cls.objects(pk=task_id).update(
            **update_query,
        )

    @classmethod
    def _get_tasks_dict(cls):
        from app.accruals.tasks import receipt_tasks
        return receipt_tasks.__dict__


def create_receipt_task(author_id, provider_id, provider_name, subtask_name,
                        doc_id=None, mass_operation=False, houses=None,
                        period=None, parent=None, house_id=None,
                        autorun=True,
                        **kwargs):
    task = ReceiptPDFTask(
        doc=doc_id,
        accounts_filter=kwargs.get('filter_id'),
        author=author_id,
        provider=ProviderEmbedded(
            id=provider_id,
            str_name=provider_name
        ),
        name='create_receipt_task',
        url=kwargs.get('page_url'),
        houses=houses,
        period=period,
        parent=parent,
        house=house_id,
    )
    task.save()
    if not mass_operation:
        task.tasks.append(
            SubTask(
                name=subtask_name,
                kwargs=kwargs,
            ),
        )
    else:
        for sub_task_args in kwargs['kwargs']:
            task.tasks.append(
                SubTask(
                    name=subtask_name,
                    kwargs=sub_task_args,
                ),
            )
    task.state = 'new'
    task.save()
    if autorun:
        task.run(task.pk)
    return task.pk
