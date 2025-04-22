from datetime import datetime, timedelta
from mongoengine import Document, DateTimeField, StringField, ReferenceField, \
    IntField, ListField, ObjectIdField

from lib.archive import create_zip_file_in_gs
from lib.gridfs import put_file_to_gridfs
from processing.models.billing.files import Files

from processing.models.mixins import EveFix
import settings


class TaskStatus(object):
    CREATED = 'created'
    DELAYED = 'delayed'
    PARSING = 'PARSING'
    PARSED = 'parsed'
    SAVING = 'saving'
    WORK_IN_PROGRESS = 'work_in_progress'
    DONE = 'done'
    ERROR = 'error'


TASK_STATUS_CHOICES = (
    (TaskStatus.CREATED, "Создана"),
    (TaskStatus.DELAYED, "Отложена"),
    (TaskStatus.PARSING, "Идет парсинг"),
    (TaskStatus.PARSED, "Парсинг заверешен"),
    (TaskStatus.SAVING, "Сохранение результатов"),
    (TaskStatus.WORK_IN_PROGRESS, "Выполняется"),
    (TaskStatus.DONE, "Выполнена"),
    (TaskStatus.ERROR, "Ошибка"),
)


class Task(Document, EveFix):
    meta = {
        "db_alias": "queue-db",
        'allow_inheritance': True,
        'index_background': True,
        'auto_create_index': False,
    }
    # TODO: drop when processing will be moved to celery
    release = StringField(default=settings.RELEASE)
    celery_task_name = StringField()
    uuid = StringField()

    # TODO: drop when processing will be moved to celery
    parent = ReferenceField('processing.models.tasks.Task')

    # "Идентификатор очереди"
    # TODO: drop when processing will be moved to celery
    queue = StringField(required=True)

    # "Время создания"
    # TODO: drop when processing will be moved to celery
    created = DateTimeField(required=True,
                            default=datetime.now)

    # "Время запуска"
    # TODO: drop when processing will be moved to celery
    started = DateTimeField()

    # "Отложено до"
    # TODO: drop when processing will be moved to celery
    delayed = DateTimeField()

    # "Время завешения"
    # TODO: drop when processing will be moved to celery
    ended = DateTimeField()

    # "Приоритет"
    # больше = приоритетнее
    # TODO: drop when processing will be moved to celery
    priority = IntField(default=10)

    # "Worker ID"
    # TODO: drop when processing will be moved to celery
    worker_pid = StringField()

    # "Статус"
    status = StringField(required=True,
                         choices=TASK_STATUS_CHOICES,
                         default=TaskStatus.CREATED)
    # Лог
    log = ListField(StringField(), default=[])

    # "Возникшее исключение"
    # TODO: drop when processing will be moved to celery
    exception = StringField()

    # "Номер лицевого счета"
    # TODO: drop when processing will be moved to celery
    account = IntField()

    offset_account = ObjectIdField()
    offset_sector = StringField()

    def process(self, *args, **kwargs):
        raise NotImplementedError


class RequestTask(Task):

    queue = StringField(verbose_name="Идентификатор очереди", default='request_task')
    children_queue = StringField(verbose_name="Идентификатор очереди для создаваемых подзадач", default='general')
    origin = StringField(verbose_name="Источник запроса", default='UNKNOWN')

    def create_child_task(self, cls, **keys):
        params = dict(
            queue=self.children_queue,
            status=TaskStatus.CREATED,
            created=datetime.now(),
            parent=self,
            provider=self.provider,  # TODO убрать после реализации прав (заменить на наследование прав от реквеста)
        )

        params.update(keys)
        return cls(**params)

    def process(self, *args, **kwargs):
        raise NotImplementedError


class ZipSiblingsFilesTask(Task):
    DESCRIPTION = 'Задача по созданию zip-архива'

    filename = StringField(required=True, verbose_name="Имя файла итогового архива")
    file_uuid = StringField()
    # file = FileField(db_alias='files-db')
    file = ObjectIdField()

    # TODO убрать после реализации прав (заменить на наследование прав от реквеста)
    # Сейчас добавлено для фильтрации задач по организации, от которой производится запрос
    provider = ReferenceField('processing.models.billing.provider.Provider', verbose_name="Организация", required=True)

    def process(self, *args, **kwargs):

        self.status = TaskStatus.WORK_IN_PROGRESS
        self.started = datetime.now()
        self.save()

        all_siblings = Task.objects(parent=self.parent).as_pymongo()
        pending_tasks = [
            task
            for task in all_siblings
            if task["_cls"] != "Task.ZipSiblingsFilesTask"
        ]

        # Если хоть одна из соседних задач закончилась с ошибкой, формирование zip-архива тоже считаем завершенным с ошибкой
        if any((pt['status'] == TaskStatus.ERROR for pt in pending_tasks)):
            self.ended = datetime.now()
            self.status = TaskStatus.ERROR
            self.save()
            return

        # Если не все соседние задачи в статусе done - откладываем создание zip на 1 минуту
        if not all((pt['status'] == TaskStatus.DONE for pt in pending_tasks)):
            self.delayed = datetime.now() + timedelta(seconds=10)
            self.status = TaskStatus.CREATED
            self.save()
            return

        # zip_file = InMemoryZipFile()
        # done_files = [
        #     (task.filename, task.file) for task in pending_tasks if
        #
        #     task.status == TaskStatus.DONE and
        #     getattr(task, 'filename', None) and
        #     getattr(task, 'file', None)
        # ]

        file_uuid, file_id = create_zip_file_in_gs(
            self.filename, 'Provider', self.parent.provider.id,
            gs_ids=[task['file'] for task in pending_tasks],
            id_return=True
        )
        self.file = file_id
        self.file_uuid = file_uuid

        # for name, done_file in done_files:
        #     data = done_file.read()
        #     if data:
        #         zip_file.add_file(name, data)
        #     else:
        #         GisFileProcessingStatus(
        #             status='file {} {} not found'.format(
        #                 done_file.gridout._id, name),
        #             task=self.pk,
        #             request=self.parent.id,
        #             is_error=True,
        #         ).save()
        # for name, done_file in done_files:
        #     done_file.delete()

        # self.file_uuid = uuid.uuid4().hex
        #
        # zip_file.seek(0)
        #
        # self.file.put(
        #     zip_file,
        #     filename=self.filename,
        #     uuid=self.file_uuid,
        #     content_type='application/zip',
        #     owner_resource='Provider',
        #     owner_id=self.parent.provider.id
        # )

        self.status = TaskStatus.DONE
        self.ended = datetime.now()
        self.save()


class TaskMixin:
    description = StringField(verbose_name='Описание возникающих ошибок')
    updated = DateTimeField(verbose_name='Дата последнего обновления')
    created = DateTimeField(
        default=datetime.now,
        verbose_name='Дата создания'
    )
    file = ObjectIdField(
        null=True,
        verbose_name='file_id в GridFS'
    )
    state = StringField(
        verbose_name='Состояние отсылки',
        choices=(
            'failed',
            'ready',
            'wip',
            'new'
        )
    )

    def save(self, *arg, **kwargs):
        self.updated = datetime.now()
        return getattr(super(), 'save')(*arg, **kwargs)

