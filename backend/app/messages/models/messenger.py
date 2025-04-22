import collections
import json
from datetime import datetime

from asgiref.sync import async_to_sync
from bson import ObjectId
from mongoengine import (
    EmbeddedDocument,
    StringField,
    BooleanField,
    ListField,
    IntField,
    ObjectIdField,
    DateTimeField,
    DictField,
    Document,
    EmbeddedDocumentListField,
    EmbeddedDocumentField,
    ValidationError,
)

from api.v4.serializers import json_serializer
from app.messages.models.choices import OBJECT_CHOICES
from constants.common import TASK_STATES
import logging

logger = logging.getLogger('c300')


class ReportMessageExtraEmbeddedSchema(EmbeddedDocument):
    task_id = StringField(verbose_name="Id задачи и сообщения")
    only_xlsx = BooleanField(
        verbose_name="Отчёт только для скачивания",
        default=False,
    )
    progress = ListField(
        IntField(),
        default=[0, 1],
        verbose_name="Прогресс построения",
    )
    state = StringField(
        choices=TASK_STATES
    )


class MessageEmbeddedMixin:
    id = ObjectIdField()
    created = DateTimeField(default=datetime.now)
    obj = StringField(
        verbose_name="Объект задачи",
        choices=OBJECT_CHOICES
    )
    text = StringField(verbose_name="Сообщение пользователю")
    url = StringField(verbose_name="Ссылка по которой нужно перейти")
    count = IntField(verbose_name="Количество непрочитанных сообщений")
    unread = BooleanField(default=True)


class MessageEmbedded(MessageEmbeddedMixin, EmbeddedDocument):
    pass


class ReportMessageEmbedded(MessageEmbeddedMixin, EmbeddedDocument):
    extra = DictField(verbose_name="Доп. инфа")

    def validate_extra(self):
        if self.obj == OBJECT_CHOICES:
            self.validate_report_data(self.extra)

    @staticmethod
    def validate_report_data(data):
        ReportMessageExtraEmbeddedSchema(**data).validate()


class UserTasks(Document):
    """ Сообщения по списку пользовательских задач """
    meta = {
        'db_alias': 'cache-db',
        'collection': 'messenger',
        'index_background': True,
        'auto_create_index': False,
        'strict': False,
        'indexes': [
            'account',
        ],
    }
    account = ObjectIdField(verbose_name="ID пользователя")
    reports = EmbeddedDocumentListField(
        ReportMessageEmbedded,
        verbose_name="Список отчетов и их состояний"
    )
    gis = EmbeddedDocumentListField(
        MessageEmbedded,
        verbose_name="Задачи по ГИС"
    )
    journal = EmbeddedDocumentField(
        MessageEmbedded,
        verbose_name="Журнал заявок"
    )
    news = EmbeddedDocumentField(
        MessageEmbedded,
        verbose_name="Новости"
    )
    ticket = EmbeddedDocumentField(
        MessageEmbedded,
        verbose_name="Обращения"
    )
    cash = EmbeddedDocumentField(
        MessageEmbedded,
        verbose_name="Платежки, которые пора фискалить"
    )
    registry = EmbeddedDocumentField(
        MessageEmbedded,
        verbose_name="Реестры"
    )
    meters = EmbeddedDocumentListField(
        MessageEmbedded,
        verbose_name="Импорт показаний счетчиков"
    )
    messages = EmbeddedDocumentListField(
        MessageEmbedded,
        verbose_name="Список других сообщений"
    )
    receipts = EmbeddedDocumentListField(
        MessageEmbedded,
        verbose_name="Квитанции"
    )
    coefs = EmbeddedDocumentField(
        MessageEmbedded,
        verbose_name="Импорт квартирных коэффициентов"
    )
    own_contract_docs = EmbeddedDocumentListField(
        MessageEmbedded,
        verbose_name="Экспорт архивных документов и актов сверок"
    )
    accrual_docs = EmbeddedDocumentListField(
        MessageEmbedded,
        verbose_name="Документы начислений"
    )
    houses_accrual_docs = EmbeddedDocumentListField(
        MessageEmbedded,
        verbose_name="Документы начислений по домам"
    )
    massive_receipts = EmbeddedDocumentListField(
        MessageEmbedded,
        verbose_name="Массовая печать квитанций"
    )

    # удалить после деплоя задачи 379913
    service_recalculation = EmbeddedDocumentListField(
        MessageEmbedded,
        verbose_name="Массовый перерасчёт услуг"
    )
    penalty_recalculation = EmbeddedDocumentListField(
        MessageEmbedded,
        verbose_name="Массовый перерасчёт пеней"
    )
    mass_create_accrual_doc = EmbeddedDocumentListField(
        MessageEmbedded,
        verbose_name="Массовое создание документов начислений"
    )
    rosreestr = EmbeddedDocumentListField(
        MessageEmbedded,
        verbose_name="Получение данных из росреестра"
    )

    def save(self, *args, **kwargs):
        for msg in self.reports:
            msg.validate_extra()
        super().save(*args, ** kwargs)

    @classmethod
    def create_report_task(cls, account_id, task_id: str, page_url: str,
                           name: str, only_xlsx: bool = False,
                           progress: list = None, report_id=None,
                           meta: dict = None, report_name: str =None):
        user_tasks = UserTasks.get_messenger(account_id)
        extra_data = {
            'task_id': task_id,
            'url': page_url,
            'state': 'PENDING',
            'only_xlsx': only_xlsx,
        }
        if progress:
            extra_data['progress'] = progress
        if report_id:
            extra_data['report_id'] = report_id
        if report_name:
            extra_data['report_name'] = report_name
        if meta:
            extra_data.update(meta)
        msg = ReportMessageEmbedded(
            obj='report',
            text=f'Отчёт: {name}',
            extra=extra_data,
        )
        msg.validate_extra()
        cls.objects(
            pk=user_tasks.pk,
        ).update(
            push__reports=msg,
        )
        cls.ws_notify(account_id)

    def clean_report_tasks(self):
        text_value_list = ['success', 'failed', 'finished']
        self.__class__.objects(
            pk=self.pk,
        ).update(
            __raw__={
                '$pull': {
                    'reports': {'extra.state': 'FAILURE'},
                    'receipts': {'text': {'$in': text_value_list}},
                    'massive_receipts': {
                        'text': {'$in': text_value_list}
                    },
                    'service_recalculation': {
                        'text': {'$in': text_value_list}
                    },
                    'penalty_recalculation': {
                        'text': {'$in': text_value_list}
                    },
                    'mass_create_accrual_doc': {
                        'text': {'$in': text_value_list}
                    }
                },
                '$unset': {'messages': 1},
            },
        )

    @classmethod
    def delete_report_task(cls, account_id, report_id):
        user_tasks = UserTasks.get_messenger(account_id)
        updated = cls.objects(
            pk=user_tasks.pk,
        ).update(
            __raw__={
                '$pull': {
                    'reports': {'extra.task_id': report_id},
                },
            },
        )
        if updated:
            cls.ws_notify(account_id)

    def delete_wrong_report_tasks(self, skip_save=False):
        deleted = 0
        ix = 0
        while ix < len(self.reports):
            report = self.reports[ix]
            if not report or not report.extra.get('task_id'):
                self.reports.pop(ix)
                deleted += 1
            else:
                ix += 1
        if deleted and not skip_save:
            self.save()
            self.ws_notify(self.account)
        return deleted

    @classmethod
    def set_report_state(cls, account_id, report_id, state):
        if state not in TASK_STATES:
            raise ValidationError(f'Wrong report state "{state}"')
        messenger = cls.get_messenger(account_id)
        updated = cls.objects(
            __raw__={
                '_id': messenger.pk,
                'reports.extra.task_id': report_id,
            }
        ).update(
            __raw__={
                '$set': {
                    'reports.$.extra.state': state,
                },
            },
        )
        if updated:
            cls.ws_notify(account_id)
        return bool(updated)

    @classmethod
    def update_report_progress(cls, account_id, report_id, state, progress):
        messenger = cls.get_messenger(account_id)
        updated = cls.objects(
            __raw__={
                '_id': messenger.pk,
                'reports': {
                    '$elemMatch': {
                        '$or': [
                            {'extra.task_id': report_id},
                            {'extra.report_id': report_id}
                        ]
                    }
                }
            }
        ).update(
            __raw__={
                '$set': {
                    'reports.$.extra.state': state,
                    'reports.$.extra.percent': progress
                }
            }
        )
        if updated:
            cls.ws_notify(account_id)
        return bool(updated)

    @classmethod
    def update_multireport_progress(cls, account_id, report_id):
        user_tasks = UserTasks.get_messenger(account_id)
        report = next(
            (
                x for x in user_tasks.reports
                if report_id in (
                    str(x.extra['task_id']),
                    str(x.extra.get('report_id'))
                )
            ),
            None
        )
        if not report:
            return

        updated = cls.objects(
            __raw__={
                '_id': user_tasks.pk,
                'reports': {
                    '$elemMatch': {
                        '$or': [
                            {'extra.task_id': ObjectId(report_id)},
                            {'extra.report_id': ObjectId(report_id)}
                        ]
                    }
                }
            }
        ).update(
            __raw__={
                '$inc': {
                    'reports.$.extra.progress.0': 1,
                },
            },
        )
        cls.ws_notify(account_id)
        return bool(updated)

    def clean_receipts(self, meta):
        doc_id = meta.get('doc_id')
        sectors = meta.get('sectors')
        if not doc_id:
            return
        for i, receipt in enumerate(self.receipts):
            if (
                receipt.extra.get('doc_id') == doc_id
                and receipt.extra.get('sectors') == sectors
            ):
                self.receipts.pop(i)
        self.save()

    @classmethod
    def get_messenger(cls, account_id):
        messenger = cls.objects(account=account_id).first()
        if not messenger:
            messenger = cls(
                account=account_id,
                reports=[],
                gis=[],
                journal=None,
                news=None,
                ticket=None,
                cash=None,
                receipts=[],
                meters=[],
                coefs=None,
                accrual_docs=[],
                massive_receipts=[],
                own_contract_docs=[],
            )
            messenger.save()
        return messenger

    @classmethod
    def upsert_accounts(cls, accounts_ids):
        for account_id in accounts_ids:
            cls.objects(
                account=account_id,
            ).upsert_one(
                reports=[],
                gis=[],
                journal=None,
                news=None,
                ticket=None,
                cash=None,
                receipts=[],
                meters=[],
                coefs=None,
                accrual_docs=[],
                massive_receipts=[],
                own_contract_docs=[],
            )

    @classmethod
    def receipts_updated(cls, account_id, task_id):
        messenger = cls.get_messenger(account_id)
        if messenger.receipts:
            cls.objects(
                pk=messenger.pk,
            ).update(
                __raw__={
                    '$pull': {
                        'receipts.id': task_id,
                    },
                },
            )
            cls.ws_notify(account_id)

    def clean_rosreestr(self, timer=None):
        self.__class__.objects(
            pk=self.pk,
        ).update(
            __raw__={
                '$pull': {
                    'rosreestr': {
                        'created': {
                            '$lt': timer
                        },
                    },
                },
            },
        )
        self.__class__.objects(
            pk=self.pk,
        ).update(
            __raw__={
                '$pull': {
                    'rosreestr': {
                        'text': {
                            '$in': ['failed', 'end']
                        },
                    },
                },
            },
        )

    def clean_coefs_tasks(self):
        self.__class__.objects(
            pk=self.pk,
        ).update(
            unset__coefs='',
        )
        self.ws_notify(self.account)

    @classmethod
    def clean_field(cls, field, account_id):
        messenger = cls.get_messenger(account_id)
        if hasattr(messenger, field):
            messenger.update(__raw__={'$unset': {field: 1}})

    @classmethod
    def add_simple_message(cls, account_id, section, count=None):
        """
        Добавляет ивент в мессенджер.
        Не работает с gis и reports
        """
        restrict_sections = {'gis', 'reports'}
        if section in restrict_sections:
            raise PermissionError(
                f'Метод не может работать '
                f'с этими секциями: {restrict_sections}!'
            )

        messenger = cls.get_messenger(account_id)
        new_msg = MessageEmbedded(
            text='update',
        )
        if count:
            new_msg.count = count
        setattr(messenger, section, new_msg)
        messenger.save()
        cls.ws_notify(account_id)

    @classmethod
    def send_message(cls, account_id, message, url):
        messenger = cls.get_messenger(account_id)
        cls.objects(
            pk=messenger.pk,
        ).update(
            push__messages=MessageEmbedded(
                text=message,
                url=url,
            ),
        )
        cls.ws_notify(account_id)

    @classmethod
    def send_notices(cls, accounts_ids, obj_key, message='new',
                     obj_id=None, count=0, url=''):
        """
        Общий метод добавления информации о
        новых обращении/новости/заявке в журнале
        """
        logger.debug('send_notices %s with id %s', obj_key, obj_id)
        users_tasks = cls.objects(__raw__={'account': {'$in': accounts_ids}})
        new_users = list(
            set(accounts_ids)
            - set(users_tasks.distinct('account'))
        )
        cls.upsert_accounts(new_users)
        if obj_id:
            update_queryset = users_tasks.filter(
                __raw__={
                    f'{obj_key}.id': obj_id,
                },
            )
            update_field_key = f'{obj_key}.$'
        else:
            update_queryset = users_tasks
            update_field_key = obj_key
        # Добавим уведомление для существующих
        if obj_id:
            update_set_query = {
                f'{update_field_key}.text': message,
                f'{update_field_key}.unread': True,
            }
            if url:
                update_set_query[f'{update_field_key}.url'] = url
            if count:
                update_set_query[f'{update_field_key}.count'] = count
        else:
            update_set_query = {
                update_field_key: {
                    'text': message,
                    'unread': True,
                    'url': url,
                    'count': count,
                },
            }
        res = update_queryset.update(
            __raw__={
                '$set': update_set_query,
            },
        )
        logger.debug(
            'send_notices %s with id %s updated %s',
            obj_key, obj_id, res,
        )
        if obj_id:
            res = users_tasks.filter(
                __raw__={f'{obj_key}.id': {'$ne': obj_id}},
            ).update(
                **{
                    f'push__{obj_key}': MessageEmbedded(
                        id=obj_id,
                        text=message,
                        url=url,
                        count=count,
                        unread=True,
                    ),
                }
            )
            logger.debug(
                'send_notices %s with id %s inserted %s',
                obj_key, obj_id, res,
            )
        cls.ws_notify(accounts_ids)

    @classmethod
    def ws_notify(cls, accounts):
        """
        Отправка уведомлений клиенту через WebSocket
        """
        if not isinstance(accounts, collections.Iterable):
            accounts = (accounts, )
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        for _id in accounts:  # правильно ли делать так, через цикл
            channel_name = f'updates_{str(_id)}'
            data = {
                'type': 'response.proxy',
                'event': 'get.notices',  # TODO: возможно, изменить на что-то нужное
                'data': cls.get_notices(_id),
            }
            async_to_sync(channel_layer.group_send)(
                channel_name, data
            )

    @classmethod
    def get_notices(cls, user_id):
        """
        Преобразует данные мессенджера в список сообщений
        """
        user_tasks = UserTasks.get_messenger(user_id)
        result = []
        for field_name in user_tasks:
            field_value = getattr(user_tasks, field_name, None)
            if isinstance(field_value, MessageEmbedded):
                tasks = [field_value]
            elif isinstance(field_value, list):
                tasks = {
                    v.id: v
                    for v in field_value
                    if isinstance(v, MessageEmbedded)
                }
                tasks = list(tasks.values())
            else:
                tasks = []
            for task in tasks:
                message = cls._get_message_from_task(task, field_name)
                result.append(message)
        for task in user_tasks.reports:
            message = cls._get_message_from_task(task, 'reports')
            result.append(message)
        for task in user_tasks.messages:
            message = cls._get_message_from_task(task, 'messages')
            if task.unread and message not in result:
                result.append(message)
        # user_tasks.clean_report_tasks()
        # user_tasks.clean_field('coefs', user_id)
        # user_tasks.clean_field('accrual_docs', user_id)
        return json.dumps(result, default=json_serializer, ensure_ascii=False)
        # TODO: Латиница приходит в коде юникода. Возможно, нужно преобразование

    @staticmethod
    def _get_message_from_task(task, obj_name):
        result = task.to_mongo()
        result['obj'] = obj_name
        if 'extra' in result:
            result.update(result.pop('extra'))
        return result
