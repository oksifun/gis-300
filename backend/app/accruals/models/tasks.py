import datetime
from random import random, randint

from celery import chain
from dateutil.relativedelta import relativedelta
from mongoengine import Document, ObjectIdField, DateTimeField, StringField, \
    EmbeddedDocumentListField, ListField, DictField, EmbeddedDocument, \
    BooleanField, IntField, EmbeddedDocumentField, DoesNotExist, Q

from app.accruals.cipca.tasks.mass_tasks_create import MASS_TASK_RUN_FUNCTIONS
from app.accruals.models.logs import CipcaLog
from app.accruals.tasks.caching import update_accrual_doc_cache
from app.caching.models.filters import FilterCache
from processing.models.billing.files import Files
from processing.models.choices import ACCRUAL_SECTOR_TYPE_CHOICES
from processing.models.tasks.choices import TASK_STATE_TYPE_CHOICES, \
    TaskStateType


class SubTask(EmbeddedDocument):
    name = StringField(
        required=True,
        verbose_name='Название задачи, имя функции',
    )
    kwargs = DictField(verbose_name='Параметры для передачи в функцию')
    uid = StringField(verbose_name='ID в celery')
    state = StringField(default='new', verbose_name='Текущее состояние')
    wait_prev = BooleanField(
        default=False,
        verbose_name='Ждать ли предыдущую перед запуском',
    )
    progress = IntField(default=0)


class ProviderEmbedded(EmbeddedDocument):
    """Организация автора задачи"""

    id = ObjectIdField(
        db_field='_id'
    )
    str_name = StringField(
        verbose_name='Полное наименование организации'
    )


class CommonAccrualTask(Document):
    """
    Общий класс для создания Celery-задач и сохранения их в базе.
    Работа с задачей происходит в целери асинхронно, поэтому метод save запрещён
    """
    meta = {
        'abstract': True
    }
    doc = ObjectIdField(verbose_name='Документ AccrualDoc', null=True)
    house = ObjectIdField(verbose_name='Дом', null=True)
    accounts_filter = ObjectIdField(
        verbose_name='Фильтр объектов',
        null=True,
    )
    account_id = ObjectIdField(verbose_name='Акакунт, если он один', null=True)
    created = DateTimeField(
        default=datetime.datetime.now,
        verbose_name='Дата создания',
    )
    started = DateTimeField(
        verbose_name='Дата и время начала выполнения задачи',
        null=True,
    )
    time_limit = DateTimeField(
        verbose_name='Ограничение по времени выполнения задачи',
        null=True,
    )
    updated = DateTimeField(
        verbose_name='Дата и время последнего изменения задачи',
        null=True,
    )
    period = DateTimeField(
        verbose_name='Период документов задачи',
        null=True,
    )
    author = ObjectIdField(verbose_name='Автор задачи')
    provider = EmbeddedDocumentField(
        ProviderEmbedded,
        verbose_name='Организация автора задачи',
    )
    name = StringField(verbose_name='Название задачи')
    description = StringField(verbose_name='Описание задачи для пользователя')
    state = StringField(
        choices=TASK_STATE_TYPE_CHOICES,
        default=TaskStateType.PREPARE,
        verbose_name='Текущее состояние',
    )
    tasks = EmbeddedDocumentListField(
        SubTask,
        verbose_name='Подзадачи - последовательность действий',
    )
    log = ListField(StringField(), verbose_name='Лог')
    messages = ListField(DictField(), verbose_name='Сообщения для пользователя')
    url = StringField(
        default='',
        null=True,
        verbose_name='Страница, на которой была создана задача',
    )
    parent = ObjectIdField(verbose_name='Родительская задача')

    RUNABLE_STATES = ('new', 'wip')

    def save(self, *args, **kwargs):
        if self._created:
            super().save(*args, **kwargs)
            return
        old_state = self.__class__.objects(pk=self.pk).get().state
        if old_state == 'prepare':
            super().save(*args, **kwargs)
        else:
            raise PermissionError('Method "save" is restricted, use "update"')

    @classmethod
    def add_log_message(cls, task_id, message, field='log'):
        cls.objects(
            pk=task_id,
        ).update(
            **{f'push__{field}': f'{datetime.datetime.now()} {message}'},
        )

    @classmethod
    def change_sub_task_state(cls, task_id, task_ix, task_name, state,
                              kwargs_params):
        raise NotImplementedError()

    @classmethod
    def change_task_state(cls, task_id, task_name, sub_task_state):
        raise NotImplementedError()

    @classmethod
    def run(cls, task_id, auto_execute=True, forced=False, lock_key=None):
        tasks = cls._get_tasks_dict()
        task_instance = cls.objects(pk=task_id).get()
        task_instance.update(
            lock_key=lock_key,
            state=TaskStateType.PREPARE,
        )
        run = []
        for ix, task in enumerate(task_instance.tasks):
            if forced:
                if task.state not in cls.RUNABLE_STATES:
                    continue
            elif task.state != TaskStateType.NEW:
                continue
            if task.wait_prev and run:
                break
            params = dict(
                task_id=task_instance.id,
                sub_task_ix=ix,
            )
            if lock_key:
                params.update(lock_key=lock_key)
            if auto_execute:
                celery_task = tasks.get(task.name).delay(**params)
                run.append(celery_task.id)
            else:
                celery_task = tasks.get(task.name).s(**params)
                run.append(celery_task)
            cls.objects(
                pk=task_id,
            ).update(
                **{f'set__tasks__{ix}__uid': celery_task.id},
            )
        return run

    @classmethod
    def _get_tasks_dict(cls):
        raise NotImplemented()


class CipcaTask(CommonAccrualTask):
    """
    Задача обращения к Cipca - расчёт начислений по квартплате.
    Работа с задачей происходит в целери асинхронно, поэтому метод save запрещён
    """
    meta = {
        'db_alias': 'queue-db',
        'collection': 'cipca_tasks',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'doc',
            '-time_limit',
            ('state', '-created'),
        ],
    }
    # todo DEPRECATED
    providers = ListField(
        ObjectIdField(),
        verbose_name='Список организаций, присутствующих в документе',
    )
    month = DateTimeField(verbose_name='Месяц документа - денормализация')
    lock_key = StringField()

    @classmethod
    def _get_tasks_dict(cls):
        from app.accruals.tasks.pipca import tasks
        return tasks.__dict__

    @classmethod
    def change_sub_task_state(cls, task_id, task_ix, task_name, state,
                              kwargs_params=None, time_limit_secs=None):
        timestamp = datetime.datetime.now()
        CipcaLog.write_log(
            task_id,
            f'{timestamp} ix{task_ix} {task_name} changed to {state}',
        )
        update_dict = {
            f'set__tasks__{task_ix}__state': state,
            'set__updated': timestamp,
        }
        if kwargs_params:
            for key, value in kwargs_params.items():
                update_dict[f'set__tasks__{task_ix}__kwargs__{key}'] = value
        cls.objects(
            pk=task_id,
        ).update(
            **update_dict,
        )
        cls.change_task_state(task_id, task_name, state, time_limit_secs)

    @classmethod
    def change_task_state(cls, task_id, task_name, sub_task_state,
                          time_limit_secs=None):
        state = None
        update_dict = dict()
        task = cls.objects(pk=task_id).get()
        if sub_task_state == 'wip' and task.state == 'new':
            date_now = datetime.datetime.now()
            update_dict.update(
                {
                    'set__started': date_now,
                    'set__time_limit': (
                            date_now
                            + relativedelta(seconds=time_limit_secs)
                    ),
                },
            )
            state = sub_task_state
        if sub_task_state in ('failed', 'finished'):
            if all(map(lambda m: m.state == 'failed', task.tasks)):
                state = 'failed'
            elif all(
                    map(
                        lambda m: m.state in ('finished', 'failed'),
                        task.tasks,
                    ),
            ):
                state = 'finished'
                cls.run_after_tasks(
                    task.extract_docs_ids(),
                    parent_task_id=task.parent,
                )
        if state:
            timestamp = datetime.datetime.now()
            CipcaLog.write_log(
                task_id,
                f'{timestamp} {task_name} changed to {state}',
            )
            update_dict.update(set__state=state)
            cls.objects(
                pk=task_id,
            ).update(
                **update_dict,
            )

    def extract_docs_ids(self):
        result = {self.doc} if self.doc else set()
        for task in self.tasks:
            if task.kwargs.get('doc'):
                result.add(task.kwargs['doc'])
        return result

    def extract_houses_ids(self, as_string=False):
        houses = [
            task.kwargs.get('house')
            for task in self.tasks
            if task.kwargs.get('house')
        ]
        if as_string:
            houses = list(map(str, houses))
        return houses

    @classmethod
    def run_after_tasks(cls, docs_ids, parent_task_id=None):
        for doc_id in docs_ids:
            update_accrual_doc_cache.delay(doc_id, parent_task_id)

    def extract_accounts_ids(self):
        if self.account_id:
            return [self.account_id]
        if self.accounts_filter:
            try:
                return FilterCache.extract_objs(self.accounts_filter)
            except DoesNotExist:
                return [self.accounts_filter]
        return None


class HousesCalculateTaskFilter(EmbeddedDocument):
    fias = ListField(
        StringField(),
        verbose_name='Список aoguid ФИАС для фильтрации домов',
    )
    houses = ListField(
        ObjectIdField(),
        verbose_name='Список id домов',
    )


class HousesCalculateTask(Document):
    meta = {
        'db_alias': 'queue-db',
        'collection': 'cipca_houses_tasks',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('provider', '-created', 'state'),
        ],
    }
    provider = ObjectIdField(verbose_name='Организация-владелец')
    author = ObjectIdField(verbose_name='Сотрудник автор задачи')
    created = DateTimeField(default=datetime.datetime.now)
    houses_filter = EmbeddedDocumentField(
        HousesCalculateTaskFilter,
        verbose_name='Фильтр домов для расчёта',
    )
    total_tasks = IntField(
        verbose_name='Нужное кол-во задач по расчёту',
    )
    ready_tasks = IntField(
        default=0,
        verbose_name='Кол-во законченных задач по расчёту',
    )
    houses_processed = IntField(
        default=0,
        verbose_name='Кол-во обработанных домов',
    )
    failed_tasks = IntField(
        default=0,
        verbose_name='Кол-во упавших задач по расчёту',
    )
    updated = DateTimeField(
        verbose_name='Дата и время последнего изменения задачи',
        null=True,
    )
    month = DateTimeField(
        required=True,
        verbose_name='Период документов задачи',
    )
    date = DateTimeField(
        required=False,
        verbose_name='Дата документов задачи',
        null=True,
    )
    name = StringField(verbose_name='Название задачи')
    state = StringField(
        choices=TASK_STATE_TYPE_CHOICES,
        default=TaskStateType.NEW,
        verbose_name='Текущее состояние',
    )
    params = DictField(
        verbose_name='Дополнительные параметры вызова функций расчёта',
    )
    lock_key = StringField()

    TASKS_BATCH_SIZE = 8
    TIMEOUT_SECONDS = 60 * 6
    CIPCA_TODO_STATES = [
        TaskStateType.WIP,
        TaskStateType.NEW,
        TaskStateType.SAVING,
        TaskStateType.PREPARE,
    ]
    CIPCA_WIP_STATES = [
        TaskStateType.WIP,
        TaskStateType.SAVING,
        TaskStateType.PREPARE,
    ]
    _CACHE_SEARCH_BATCH_SIZE = 10

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.name == "mass_create_receipts":
            from processing.models.tasks.receipt import ReceiptPDFTask
            self.child_task_class = ReceiptPDFTask
        else:
            self.child_task_class = CipcaTask

    @classmethod
    def check_caching_state(cls, head_task_id):
        queryset = cls.objects(pk=head_task_id)
        task = queryset.only(
            'id',
            'state',
            'author',
        ).as_pymongo().get()
        if task['state'] != TaskStateType.CACHING:
            return False
        if cls.has_caching_docs_in_progress(head_task_id):
            return False
        queryset.update(state=TaskStateType.FINISHED)
        cls.send_finish_messages(
            task['_id'],
            task['author'],
            task.get('params', {}).get('url'),
        )

    @classmethod
    def has_caching_docs_in_progress(cls, head_task_id):
        child_docs = CipcaTask.objects(
            parent=head_task_id,
            state__in=TaskStateType.FINISHED,
        ).distinct(
            'doc',
        )
        _from = 0
        _till = cls._CACHE_SEARCH_BATCH_SIZE
        from app.accruals.models.accrual_document import AccrualDoc
        docs_queryset = AccrualDoc.objects(
            caching_wip=True,
        ).only(
            'id',
        ).as_pymongo()
        while _from < len(child_docs):
            doc = docs_queryset.filter(
                pk__in=child_docs[_from: _till],
            ).first()
            if doc:
                return True
            _from += cls._CACHE_SEARCH_BATCH_SIZE
            _till += cls._CACHE_SEARCH_BATCH_SIZE
        return False

    @classmethod
    def set_house_processed(cls, head_task_id, tasks_num):
        queryset = cls.objects(pk=head_task_id)
        if tasks_num != 1:
            queryset.update(
                inc__total_tasks=tasks_num - 1,
            )

    @classmethod
    def update_processed_houses_number(cls, head_task_id, num):
        cls.objects(
            pk=head_task_id,
        ).update(
            inc__houses_processed=num,
            inc__ready_tasks=num,
        )

    def cancel_house_tasks(self, house_id):
        task = self.child_task_class(
            author=self.author,
            provider=ProviderEmbedded(
                id=self.provider,
            ),
            period=self.month,
            parent=self.id,
            house=house_id,
            state=TaskStateType.CANCELED,
        )
        task.save()
        self.update_processed_houses_number(self.id, 1)

    @classmethod
    def add_tasks_num_for_house(cls, task_id, num):
        queryset = cls.objects(pk=task_id)
        queryset.update(
            inc__total_tasks=num,
        )

    @classmethod
    def inc_ready_tasks(cls, task_id, failed=False):
        queryset = cls.objects(pk=task_id)
        update_query = dict(
            inc__ready_tasks=1,
            updated=datetime.datetime.now(),
        )
        if failed:
            update_query.update(
                inc__failed_tasks=1,
            )
        queryset.update(**update_query)
        from app.messages.models.messenger import UserTasks
        task = queryset.only(
            'params',
            'author',
            'ready_tasks',
            'total_tasks',
        ).as_pymongo().first()
        if task:
            try:
                if task['total_tasks']:
                    progress = task['ready_tasks'] / task['total_tasks']
                else:
                    progress = 0
                if progress < 1:
                    _send_progress_messages(
                        task_id,
                        task['author'],
                        min(round(progress * 100), 100),
                    )
            except KeyError:
                pass

    def run_tasks(self, lock_key=None, forced=False):
        if self.state == TaskStateType.FINISHED:
            return 'Task was finished earlier'
        wip_tasks_num, wip_houses = self._get_wip_tasks_info()
        if len(wip_houses) >= self.TASKS_BATCH_SIZE:
            return 'Too much already run tasks'
        try:
            binds = self._get_binds()
        except DoesNotExist:
            self.update(state=TaskStateType.FAILED)
            return 'Binds not found'
        if not binds:
            return 'Binds failed'
        exist_tasks_num, exist_houses = self._get_exist_tasks_info()
        houses = self._get_houses_queryset(binds)
        houses_num = houses.count()
        tasks_created = 0
        if self.state == TaskStateType.NEW:
            self._mark_as_started(houses_num)
            tasks_created = self._create_child_tasks(houses, binds)
        elif len(exist_houses) < houses_num:
            tasks_created = self._create_child_tasks(
                houses.filter(id__nin=exist_houses),
                binds,
            )
        houses_to_run = self.TASKS_BATCH_SIZE - len(wip_houses)
        tasks_run = 0
        if houses_to_run > 0:
            tasks_run = self._run_child_tasks(houses_to_run, lock_key, forced)
        if not tasks_run:
            self.reload()
            wip_tasks_num, wip_houses = self._get_wip_tasks_info()
            finished_state = self._get_is_finished_state(wip_tasks_num)
            if finished_state:
                return finished_state
        return f'Created {tasks_created} tasks, ' \
               f'run {tasks_run} for {houses_to_run} houses'

    def _run_child_tasks(self, houses_num, lock_key, forced=False):
        queryset = self.child_task_class.objects(
            parent=self.id,
            state=TaskStateType.NEW,
        ).only(
            'id',
            'house',
        ).as_pymongo()
        houses = queryset.distinct('house')
        tasks_created = 0
        houses_to_run = self._get_houses_to_run_tasks(houses, houses_num)
        for house in houses_to_run:
            tasks = []
            for task in queryset.filter(house=house):
                celery_tasks = self.child_task_class.run(
                    task['_id'],
                    auto_execute=False,
                    lock_key=lock_key,
                    forced=forced,
                )
                tasks.extend(celery_tasks)
                CipcaLog.write_log(
                    task['_id'],
                    f'ready to run by parent {self.id} with key {lock_key}',
                )
            if len(tasks) == 1:
                tasks[0].apply_async()
            elif len(tasks) > 1:
                for task in tasks:
                    task.apply_async()
            tasks_created += len(tasks)
        return tasks_created

    @staticmethod
    def _get_houses_to_run_tasks(houses, houses_num):
        if len(houses) <= houses_num:
            return houses
        result = []
        for _ in range(houses_num + 3):
            ix = randint(0, len(houses) - 1)
            if houses[ix] not in result:
                result.append(houses[ix])
        return result

    def _create_child_tasks(self, houses_queryset, binds):
        tasks_created = 0
        for house in houses_queryset:
            tasks_created += MASS_TASK_RUN_FUNCTIONS[self.name](
                self,
                house['_id'],
                binds=binds,
                **self.params,
            )
        return tasks_created

    def _get_wip_tasks_info(self):
        wip_tasks_queryset = self.child_task_class.objects(
            parent=self.id,
            state__in=self.CIPCA_WIP_STATES,
        )
        wip_tasks_num = wip_tasks_queryset.count()
        wip_houses = wip_tasks_queryset.distinct('house')
        return wip_tasks_num, wip_houses

    def _get_exist_tasks_info(self):
        exist_tasks_queryset = self.child_task_class.objects(
            parent=self.id,
        )
        exist_tasks_num = exist_tasks_queryset.count()
        exist_houses = exist_tasks_queryset.distinct('house')
        return exist_tasks_num, exist_houses

    def _mark_as_started(self, houses_number):
        self.update(
            state=TaskStateType.WIP,
            total_tasks=houses_number,
            ready_tasks=0,
            houses_processed=0,
            failed_tasks=0,
            updated=datetime.datetime.now(),
        )
        self.total_tasks = houses_number
        self.ready_tasks = 0
        self.houses_processed = 0

    def _get_is_finished_state(self, wip_tasks_num):
        if self.state == TaskStateType.NEW:
            return None
        result = None
        if self.ready_tasks >= self.total_tasks:
            if wip_tasks_num == 0:
                result = 'Marked as finished'
            else:
                time_limit = (
                        self.updated
                        + relativedelta(seconds=self.TIMEOUT_SECONDS)
                )
                if time_limit >= datetime.datetime.now():
                    result = 'Marked as finished by time out'
        if not result:
            return result
        if self.has_caching_docs_in_progress(self.id):
            self.update(state=TaskStateType.CACHING)
            return result
        self.update(state=TaskStateType.FINISHED)
        self.send_finish_messages(self.id, self.author, self.params.get('url'))
        return result

    @classmethod
    def send_finish_messages(cls, task_id, author_id, url=None):
        _send_finish_messages(task_id, author_id, url)

    def _get_houses_queryset(self, binds):
        houses_query = {
            '$or': [],
        }
        if self.houses_filter.houses:
            houses_query['$or'].append(
                {
                    '_id': {'$in': self.houses_filter.houses},
                },
            )
        if self.houses_filter.fias:
            houses_query['$or'].append(
                {
                    'fias_addrobjs': {'$in': self.houses_filter.fias},
                },
            )
        from app.house.models.house import House
        return House.objects(
            House.get_binds_query(binds),
            __raw__=houses_query,
        ).only(
            'id',
        ).order_by(
            'id',
        ).as_pymongo()

    def _get_binds(self):
        from app.personnel.models.personnel import Worker
        from processing.models.billing.provider.main import Provider
        provider = Provider.objects(pk=self.provider).get()
        if not self.author:
            return provider._binds_permissions
        author = Worker.objects(
            Worker.get_binds_query(provider._binds_permissions),
            pk=self.author,
        ).first()
        if author:
            return author._binds_permissions
        return provider._binds_permissions


class HousesReceiptsZipTask(Document):
    meta = {
        'db_alias': 'queue-db',
        'collection': 'receipt_zip_tasks',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('provider', '-created', 'state'),
        ],
    }
    provider = ObjectIdField(verbose_name='Организация-владелец')
    author = ObjectIdField(verbose_name='Сотрудник автор задачи')
    created = DateTimeField(default=datetime.datetime.now)
    houses_filter = EmbeddedDocumentField(
        HousesCalculateTaskFilter,
        verbose_name='Фильтр домов для поиска квитанций',
    )
    sectors = ListField(
        StringField(choices=ACCRUAL_SECTOR_TYPE_CHOICES),
        verbose_name='Направления для поиска квитанций',
    )
    total_docs = IntField(
        verbose_name='Всего найдено документов с квитанциями',
    )
    ready_docs = IntField(
        default=0,
        verbose_name='Сколько документов уже обработано',
    )
    month = DateTimeField(
        required=True,
        verbose_name='Период документов задачи',
    )
    state = StringField(
        choices=TASK_STATE_TYPE_CHOICES,
        default=TaskStateType.NEW,
        verbose_name='Текущее состояние',
    )
    result_files = EmbeddedDocumentListField(
        Files,
        verbose_name='Файлы с квитанциями',
    )
    finish_time = DateTimeField(verbose_name='Время окончания задачи')
    updated = DateTimeField(verbose_name='Время последнего обновления')
    is_deleted = BooleanField()

    @classmethod
    def get_binds_query(cls, binds):
        return Q(
            provider=binds.pr,
        )

    @classmethod
    def update_progress(cls, task_id, docs_number, author_id, progress):
        cls.objects(
            pk=task_id,
        ).update(
            ready_docs=docs_number,
            updated=datetime.datetime.now(),
        )
        cls.send_progress_messages(
            task_id,
            author_id,
            progress,
        )

    def get_accrual_docs_queryset(self):
        from app.accruals.models.accrual_document import AccrualDoc
        binds = self._get_binds()
        if not binds:
            raise DoesNotExist()
        queryset = AccrualDoc.objects(
            AccrualDoc.get_binds_query(binds),
            date_from=self.month,
        )
        houses_query = {
            '$or': [],
        }
        if self.houses_filter.houses:
            houses_query['$or'].append(
                {
                    'house._id': {'$in': self.houses_filter.houses},
                },
            )
        if self.houses_filter.fias:
            houses_query['$or'].append(
                {
                    'house.fias_addrobjs': {'$in': self.houses_filter.fias},
                },
            )
        if houses_query['$or']:
            queryset = queryset.filter(__raw__=houses_query)
        return queryset

    def _get_binds(self):
        from app.personnel.models.personnel import Worker
        from processing.models.billing.provider.main import Provider
        provider = Provider.objects(pk=self.provider).get()
        if not self.author:
            return provider._binds_permissions
        author = Worker.objects(
            Worker.get_binds_query(provider._binds_permissions),
            pk=self.author,
        ).first()
        if author:
            return author._binds_permissions
        return provider._binds_permissions

    @classmethod
    def send_finish_messages(cls, task_id, author_id):
        _send_finish_messages(task_id, author_id, '')

    @classmethod
    def send_error_messages(cls, task_id, author_id):
        _send_error_messages(task_id, author_id, '')

    @classmethod
    def send_progress_messages(cls, task_id, author_id, progress):
        _send_progress_messages(
            task_id,
            author_id,
            progress,
        )


def _send_finish_messages(task_id, author_id, url=None):
    from app.messages.models.messenger import UserTasks
    UserTasks.send_notices(
        [author_id],
        obj_key='houses_accrual_docs',
        message='update',
        obj_id=task_id,
        count=100,
        url=url,
    )
    UserTasks.send_message(
        author_id,
        'Формирование архива квитанций завершено',
        url=url,
    )


def _send_error_messages(task_id, author_id, url=None):
    from app.messages.models.messenger import UserTasks
    UserTasks.send_notices(
        [author_id],
        obj_key='houses_accrual_docs',
        message='update',
        obj_id=task_id,
        count=100,
        url=url,
    )
    UserTasks.send_message(
        author_id,
        'Ошибка при формировании архива квитанций',
        url=url,
    )


def _send_progress_messages(task_id, author_id, progress, url=None):
    from app.messages.models.messenger import UserTasks
    UserTasks.send_notices(
        [author_id],
        obj_key='houses_accrual_docs',
        message='progress',
        obj_id=task_id,
        count=progress,
        url=url,
    )
