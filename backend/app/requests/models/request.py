import datetime
from random import randint

from bson import ObjectId
from jinja2 import Environment, FileSystemLoader
from mongoengine import (
    Document,
    EmbeddedDocumentField,
    EmbeddedDocument,
    ObjectIdField,
    StringField,
    ListField,
    DateTimeField,
    DateField,
    BooleanField,
    EmbeddedDocumentListField,
    IntField,
    ReferenceField,
    ValidationError,
    FloatField,
    Q,
    DoesNotExist,
    EmailField,
)

from api.v4.telephony.models.history import CallHistory
from api.v4.telephony.consts import PERIOD_OF_BINDING_REQUEST_TO_CALLS
import settings
from app.telephony.models.base_fields import RequestEmbedded
from app.telephony.models.call_log_history import Calls
from app.area.models.area import Area
from app.house.models.house import House
from app.messages.core.email.extended_mail import TicketMail
from app.notifications.tasks.events.requests_notify import \
    send_request_notification
from app.personnel.models.denormalization.worker import \
    WorkerPositionDenormalized
from app.requests.models.embedded_docs import EmbeddedMonitoring, \
    EmbeddedStatusChange
from app.setl_home.core.choices import REQUEST_STATUS_SETL_HOME, \
    SetlRequestStatus
from app.tickets.models.tenants import Ticket
from lib.gridfs import get_file_from_gridfs, put_file_to_gridfs
from app.messages.tasks.users_tasks import \
    update_users_journals
from processing.data_producers.associated.base import get_binded_houses
from processing.models.billing.embeddeds.base import DenormalizedEmbeddedMixin
from processing.models.billing.log import History
from processing.models.billing.provider.main import Provider
from processing.models.billing.account import Tenant, OtherTenant
from app.personnel.models.personnel import Worker
from processing.models.billing.base import BindedModelMixin, \
    ProviderHouseGroupBinds, ProviderBinds
from processing.models.billing.common_methods import get_house_groups, \
    get_area_house_groups
from processing.models.billing.embeddeds.phone import DenormalizedPhone
from processing.models.billing.files import Files
from processing.models.billing.sms_message import SMSMessage
from processing.models.choices import (
    INTERCOM_STATUS_CHOICES,
    REQUEST_SAMPLES_TYPES_CHOICES,
)
from app.requests.models.choices import (
    RequestStatus,
    RequestPayStatus,
    REQUEST_PAY_STATUS_CHOICES,
    REQUEST_TAGS_CHOICES,
    REQUEST_STATUS_CHOICES, RequestTag, REQUEST_PAYABLE_TYPE_CHOICES,
    RequestPayableType,
)
from processing.references.requests import FAST_KINDS, FAST_KINDS_REVERSED


def get_request_mail_template():
    """
    Загрузка шаблона для письма, информируеющего работников об изменении
    исполнителя заявки.
    """
    template_name = 'requests.html'
    template_path = './templates/jinja/mail'
    # Загрузка окружения для их наследования
    env = Environment(loader=FileSystemLoader(template_path))
    template = env.get_template(template_name)
    return template


class DispatcherProviderDenormalized(DenormalizedEmbeddedMixin,
                                     EmbeddedDocument):
    DENORMALIZE_FROM = 'Provider'

    id = ObjectIdField(db_field="_id")
    business_types = ListField(ObjectIdField())
    str_name = StringField(verbose_name="Название организации", null=True)
    secured_ip = ListField(StringField())


class RequestDispatcherDenormalized(DenormalizedEmbeddedMixin,
                                    EmbeddedDocument):
    DENORMALIZE_FROM = 'Worker'

    id = ObjectIdField(db_field="_id", null=True)
    str_name = StringField(null=True)
    _type = ListField(StringField())
    short_name = StringField(null=True)
    provider = EmbeddedDocumentField(DispatcherProviderDenormalized)
    phones = EmbeddedDocumentListField(DenormalizedPhone)
    position = EmbeddedDocumentField(WorkerPositionDenormalized)


class EmbeddedControlInfo(EmbeddedDocument):
    desc = StringField(null=True, verbose_name='описание записи контроля')
    worker = ObjectIdField(null=True, verbose_name='автор записи о контроле')

    worker_short_name = StringField(null=True)
    position = ObjectIdField(null=True)
    position_name = StringField(null=True)


class EmbeddedAction(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')  # TODO Видимо лишнее, но в базе есть
    action = ObjectIdField(required=True)
    dt_from = DateTimeField()
    dt_till = DateTimeField()
    standpipes = ListField(ObjectIdField())
    lifts = ListField(ObjectIdField())


class EmbeddedRate(EmbeddedDocument):
    """
    Оценка для списка оценок по заявке
    """
    account = ObjectIdField()
    rate = IntField(
        null=True,
        min_value=1,
        max_value=5,
        verbose_name='Оценка заявки данным жителем'
    )
    date = DateTimeField(default=datetime.datetime.now)


class EmbeddedCommercialData(EmbeddedDocument):
    id = ObjectIdField(db_field='_id', default=ObjectId)
    is_partially_completed = BooleanField(
        verbose_name='Выполнена частично',
        null=True,
    )
    pay_status = StringField(
        required=False,
        choices=REQUEST_PAY_STATUS_CHOICES,
        default=RequestPayStatus.NOT_PAID,
        verbose_name='Статус оплаты коммерческой заявки',
    )
    warranty_period = IntField(
        min_value=0,
        verbose_name='Срок гарантии',
        null=True
    )
    payable = StringField(
        choices=REQUEST_PAYABLE_TYPE_CHOICES,
        default=RequestPayableType.NONE,
    )


class HouseEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    address = StringField()


class AreaEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id', null=True)
    number = IntField(null=True)
    str_number = StringField(null=True)
    _type = ListField(StringField())


class TenantEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id', null=True)
    number = StringField(null=True)
    str_name = StringField(null=True)
    short_name = StringField(null=True)
    phones = EmbeddedDocumentListField(
        DenormalizedPhone,
        default=[]
    )
    email = StringField(null=True)
    _type = ListField(StringField())


class OtherPersonEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    str_name = StringField(null=True)
    phones = EmbeddedDocumentListField(DenormalizedPhone)
    email = StringField(null=True)


class EmbeddedProvider(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    str_name = StringField(null=True)


class EmbeddedFile(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    uuid = StringField()
    filename = StringField()
    name = StringField()


class FileEmbedded(EmbeddedDocument):
    file = EmbeddedDocumentField(
        Files,
        null=True,
        verbose_name='Приложенный файл',
    )


class PhotoEmbedded(EmbeddedDocument):
    description = StringField(
        null=True,
        verbose_name='Описание к приложенному фото'
    )
    file = EmbeddedDocumentField(
        Files,
        null=True,
        verbose_name='Приложенный файл',
    )

    # deprecated
    id = ObjectIdField(db_field="_id", null=True)
    uuid = StringField(null=True)
    filename = StringField(null=True)
    name = StringField(null=True)


class ManuallyAddedItemEmbedded(EmbeddedDocument):
    title = StringField(
        verbose_name='Название материала/услуги',
    )
    price = IntField(
        verbose_name='Цена, установленная за единицу материала/услугу',
    )


class Request(BindedModelMixin, Document):
    # Шаблон для письма о изменении исполняющего заявку
    TEMPLATE = get_request_mail_template()
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Request',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            '_binds.pr',
            '_binds.hg',
            {
                'name': 'journal',
                'fields': [
                    '_binds.hg',
                    'common_status',
                    '-created_at',
                ],
            },
            {
                'name': 'journal_with_kinds',
                'fields': [
                    '_binds.hg',
                    'fast_kinds',
                    'common_status',
                    '-created_at',
                ],
            },
            {
                'name': 'journal_with_houses',
                'fields': [
                    'house.id',
                    'common_status',
                    '-created_at',
                ],
            },
            {
                'name': 'journal_with_executor',
                'fields': [
                    'executors',
                    'common_status',
                    '-created_at',
                ],
            },
            {
                'name': 'journal_with_executor_and_kinds',
                'fields': [
                    'executors',
                    'fast_kinds',
                    'common_status',
                    '-created_at',
                ],
            },
            {
                'name': 'journal_with_executor_and_houses',
                'fields': [
                    'executors',
                    'house.id',
                    'common_status',
                    '-created_at',
                ],
            },
            {
                'name': 'journal_with_dispatcher',
                'fields': [
                    'dispatcher.id',
                    'common_status',
                    '-created_at',
                ],
            },
            {
                'name': 'journal_with_dispatcher_and_kinds',
                'fields': [
                    'dispatcher.id',
                    'fast_kinds',
                    'common_status',
                    '-created_at',
                ],
            },
            {
                'name': 'journal_with_dispatcher_and_houses',
                'fields': [
                    'dispatcher.id',
                    'house.id',
                    'common_status',
                    '-created_at',
                ],
            },
            {
                'name': 'number_search',
                'fields': [
                    'number',
                    '-created_at',
                ],
            },
            {
                'name': 'tenant_search',
                'fields': [
                    'tenant.number',
                    '-created_at',
                ],
            },
            {
                'name': 'journal_area',
                'fields': [
                    'area.id',
                    '-created_at',
                ],
            },
            {
                'name': 'search_by_area_number',
                'fields': [
                    '_binds.pr',
                    'area.str_number',
                    '-created_at',
                ],
            },
            {
                "name": "tenants_phones",
                "fields": ["tenant.phones.str_number"],
            },
            {
                "name": "workers_phones",
                "fields": ["other_person.phones.str_number"],
            },
        ],
    }
    _binds = EmbeddedDocumentField(
        ProviderHouseGroupBinds,
        verbose_name='Привязки к организации и группе домов'
    )
    house = EmbeddedDocumentField(HouseEmbedded, verbose_name='Дом')
    area = EmbeddedDocumentField(
        AreaEmbedded,
        default=AreaEmbedded(),
        verbose_name='Квартира',
    )
    tenant = EmbeddedDocumentField(
        TenantEmbedded,
        default=TenantEmbedded(),
        verbose_name='Житель',
    )
    other_person = EmbeddedDocumentField(
        OtherPersonEmbedded,
        null=True,
        verbose_name='Другой человек'
    )
    _type = ListField(StringField())
    provider = EmbeddedDocumentField(
        EmbeddedProvider,
        verbose_name='Информация об организации'
    )
    number = StringField(verbose_name='Уникальный номер заявки')
    dispatcher = EmbeddedDocumentField(
        RequestDispatcherDenormalized,
        default=RequestDispatcherDenormalized(),
        verbose_name='Диспетчер'
    )
    kinds = ListField(
        ObjectIdField(verbose_name='Ссылка на RequestKind'),
        required=True,
        verbose_name='Динамический вид',
    )
    fast_kinds = ObjectIdField(
        choices=FAST_KINDS,
        verbose_name='ID группы kinds',
    )
    body = StringField(verbose_name='Тело заявки')
    body_sample = ObjectIdField(
        verbose_name='Ссылка на шаблон тела заявки',
        null=True,
    )
    photos = EmbeddedDocumentListField(
        PhotoEmbedded,
        verbose_name='Фотографии'
    )
    attachments = EmbeddedDocumentListField(
        FileEmbedded,
        verbose_name='Вложения',
        default=[],
    )
    completion_act_file = EmbeddedDocumentField(
        Files,
        default=Files(),
        verbose_name='Файл акта выполненных работ'
    )
    created_at = DateTimeField(
        default=datetime.datetime.now,
        required=True,
        verbose_name='Дата создания'
    )
    dt_start = DateTimeField(
        null=True,
        verbose_name='Дата и время начала работ'
    )
    dt_end = DateTimeField(
        null=True,
        verbose_name='Дата и время окончания работ'
    )
    dt_desired_start = DateTimeField(
        null=True,
        verbose_name='Желаемая дата начала работ'
    )
    dt_desired_end = DateTimeField(
        null=True,
        verbose_name='Желаемая дата окончания работ'
    )
    delayed_at = DateTimeField(verbose_name='Отложена на', null=True)
    comment = StringField(null=True, verbose_name='Описание')
    comment_sample = ObjectIdField(
        null=True,
        verbose_name='Ссылка на шаблон описания заявки'
    )
    manually_added_services = EmbeddedDocumentListField(
        ManuallyAddedItemEmbedded,
        verbose_name='Вручную добавленные услуги',
    )
    comment_works = StringField(
        null=True,
        verbose_name='Комментарий к выполненным работам',
    )
    manually_added_materials = EmbeddedDocumentListField(
        ManuallyAddedItemEmbedded,
        verbose_name='Вручную добавленные материалы',
    )
    comment_materials = StringField(
        null=True,
        verbose_name='Комментарий к материалам',
    )
    executors = ListField(ObjectIdField(), verbose_name='Исполнители')

    housing_supervision = BooleanField(
        verbose_name='Жилищный надзор (служба 004)'
    )
    administrative_supervision = BooleanField(
        null=True,
        verbose_name='Административный надзор'
    )
    show_all = BooleanField(null=True, verbose_name='Для всех в доме')
    common_status = StringField(
        choices=REQUEST_STATUS_CHOICES,
        verbose_name='Статус'
    )
    common_status_changes = EmbeddedDocumentListField(
        EmbeddedStatusChange,
        verbose_name='Изменения статусов заявки',
        default=[],
    )
    intercom_status = StringField(
        choices=INTERCOM_STATUS_CHOICES,
        null=True,
        verbose_name='Домофонщики'
    )
    cost_works = FloatField(
        default=0.0,
        null=True,
        verbose_name='Добавочная стоимость работ'
    )
    cost_materials = FloatField(
        default=0.0,
        null=True,
        verbose_name='Добавочная стоимость материалов'
    )
    control_info = EmbeddedDocumentField(
        EmbeddedControlInfo,
        default=EmbeddedControlInfo(),
        verbose_name='Контроль'
    )
    monitoring = EmbeddedDocumentField(
        EmbeddedMonitoring,
        default=EmbeddedMonitoring(),
        verbose_name='Информация по надзору за заявкой'
    )
    is_deleted = BooleanField(
        required=True,
        default=False,
        verbose_name='Заявка удалена'
    )
    actions = EmbeddedDocumentListField(
        EmbeddedAction,
        verbose_name='Отключение'
    )
    commercial_data = EmbeddedDocumentField(
        EmbeddedCommercialData,
        required=False,
        default=EmbeddedCommercialData,
        verbose_name='Данные коммерческой'
    )
    free = BooleanField(
        null=True,
        default=False,
        verbose_name='Бесплатная коммерческая заявка'
    )
    ticket = ObjectIdField(
        null=True,
        verbose_name='Ссылка на обращение',
    )
    storage_docs = BooleanField(
        default=False,
        null=True,
        verbose_name='Существует ли документ выбития'
    )
    service_doc = BooleanField(
        default=False,
        null=True,
        verbose_name='Существует ли документ услуг'
    )
    total_rate = IntField(
        null=True,
        min_value=1,
        max_value=5,
        verbose_name='Средняя оценка по заявке среди жителей',
    )
    rates = EmbeddedDocumentListField(
        EmbeddedRate,
        verbose_name='Список оценок заявки'
    )
    tags = ListField(
        StringField(choices=REQUEST_TAGS_CHOICES),
        verbose_name='Тэги для фильтрации',
    )
    has_receipt = BooleanField(verbose_name="Есть чек об оплате?")
    related_call_ids = ListField(
        ObjectIdField(),
        default=[],
        verbose_name='Связанный с заявкой звонок',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_detail = None
        self.old_state = dict(self.to_mongo())

    def __str__(self):
        request_type = "КВАРТИРНАЯ ЗАЯВКА" if "AreaRequest" in self._type else "ОБЩЕДОМОВАЯ ЗАЯВКА"
        return f"{request_type} № {self.number} от {self.created_at.strftime('%d.%m.%Y %M:%H:%S')}"

    @property
    def is_house_request(self):
        return 'HouseRequest' in self._type

    @property
    def _id(self):
        return self.id

    @property
    def is_area_request(self):
        return 'AreaRequest' in self._type

    @property
    def persons_in_charge_ids(self):
        return [x.id for x in self.monitoring.persons_in_charge]

    def append_request_to_calls(self):
        """Добавляет request в возможно связанные звонки"""
        calls = self.binded_calls()
        calls.update(__raw__={
            "$addToSet": {
                "requests": {
                    "_id": self.id,
                    "title": str(self),
                }
            }

        })

    def binded_calls(self):
        """Возможно связанные с этой заявкой звонки."""
        start_datetime = self.created_at - datetime.timedelta(
            hours=PERIOD_OF_BINDING_REQUEST_TO_CALLS
        )
        tenants_in_emb_doc = [tenant for tenant in (
            self.other_person,
            self.tenant,
        ) if tenant]
        tenants = {tenant.id for tenant in tenants_in_emb_doc}
        phones = ({
            phone.str_number for tenant in tenants_in_emb_doc
            for phone in tenant.phones
        })
        calls = CallHistory.objects(provider=self.provider.id)
        calls = calls.filter(
            Q(src__in=phones) |
            Q(dst__in=phones) |
            Q(
                caller__tenants__0__id__exists=True,
                caller__tenants__id__in=tenants,
            ) |
            Q(
                answering__tenants__0__id__exists=True,
                answering__tenants__id__in=tenants,
            )
        )
        calls = calls.filter(calldate__gte=start_datetime)
        if self.dt_end:
            finish_datetime = self.dt_end + datetime.timedelta(
                hours=PERIOD_OF_BINDING_REQUEST_TO_CALLS
            )
            calls = calls.filter(calldate__lte=finish_datetime)
        return calls

    @classmethod
    def mark_request_as_fiscalized(cls, request_id):
        query_set = cls.objects(pk=request_id)
        return query_set.update(has_receipt=True)

    @classmethod
    def binded_with_call(cls, call_id):
        """Возвращает все возможно связанные заявки со звонком call_id"""
        call = CallHistory.objects(pk=call_id).first()
        if not call:
            return []
        provider_requests = cls.objects.filter(provider__id=call.provider)
        requests_with_numbers = provider_requests.filter(
            Q(tenant__phones__str_number__in=[call.src, call.dst]) |
            Q(other_person__phones__str_number__in=[call.src, call.dst])
        )
        requests = requests_with_numbers.filter(
            Q(created_at__gte=call.calldate + datetime.timedelta(
                hours=PERIOD_OF_BINDING_REQUEST_TO_CALLS
            )) &
            (
                    Q(dt_end=None) |
                    Q(dt_end__lte=call.calldate - datetime.timedelta(
                        hours=PERIOD_OF_BINDING_REQUEST_TO_CALLS
                    ))
            )
        )
        return requests

    def _create_status_change_embedded(self):
        self.common_status_changes.append(
            EmbeddedStatusChange(status=self.common_status)
        )

    def save(self, *args, **kwargs):
        if not self.id and RequestTag.SETL_HOME not in self.tags:
            self.created_at = datetime.datetime.now()
        if not self._binds or 'provider' in self._changed_fields:
            self._binds = ProviderHouseGroupBinds(
                pr=self._get_providers_binds(),
                hg=self._get_house_binds(),
            )
        self._denormalize_fast_kinds()
        self._denormalize_refs()
        self.generate_unique_number()
        history_fields = self._catch_changed_fields()
        if self._is_triggers(['rates']):
            self.validate_rating()
            self.total_rate = self.calculate_total_rate()
        # TODO: перенести в контроллер
        if self._is_triggers(['monitoring']):
            from app.requests.core.controllers.services \
                import RequestMailService
            if len(self.monitoring.messages) \
                    > len(self.old_state['monitoring']['messages']):
                RequestMailService(
                    request=self
                ).request_monitoring_message_notify()
        new_document = self._created
        if new_document:
            self._set_persons_in_charge()
        is_dirty_executors = self._is_triggers(['executors'])
        phones_changed = self._is_triggers(['tenant', 'other_person'])
        if phones_changed:
            try:
                self.append_request_to_calls()
            except Exception:
                pass
        if self.ticket:
            if new_document:
                self._copy_photos_from_ticket()
            elif self._is_triggers(['ticket']):
                self._closed_with_created_ticket()
        if self._is_triggers(['common_status']):
            if self.service_doc:
                self._update_service_docs()
            self._create_status_change_embedded()

        change_status_for_setl = bool(
            not new_document
            and RequestTag.SETL_HOME in self.tags
            and self._is_triggers(
                ['common_status', 'comment', 'payable', 'pay_status'])
        )
        if is_dirty_executors:
            self._mirror_executor_add_to_pic()
        skip_notification = bool(kwargs.get('skip_notification'))
        obj = super().save(*args, **kwargs)
        if new_document:
            self._bind_call()

        self.__empty_monitoring_object_fields()
        if change_status_for_setl:
            self.change_status_setl_home()

        self.write_history(history_fields)
        if not skip_notification:
            self.update_users_tasks()
            self.notify_about_change(is_dirty_executors, new_document)
        # if RequestTag.CATALOGUE in self.tags and \
        #         ('common_status', RequestStatus.PERFORMED) in history_fields:
        if history_fields:
            if ('common_status', RequestStatus.PERFORMED) in history_fields:
                self.notify_performed()
        return obj

    def _bind_call(self):
        if not self.related_call_ids:
            related_call = Calls.objects(id__in=self.related_call_ids).first()
            if not related_call:
                delattr(self, 'related_call_ids')
                self.save()
            else:
                request_embedded = RequestEmbedded(
                    id=self.id,
                    body=self.body,
                )
                if not getattr(related_call, 'requests'):
                    related_call.requests = []
                related_call.requests.append(request_embedded)
                related_call.save()
        if not all((
                self.tenant,
                self.tenant.id,
                self.dispatcher,
                self.dispatcher.id,
        )):
            return
        from app.requests.tasks.linking_request_to_call import \
            bind_related_calls_after_request_save_task
        bind_related_calls_after_request_save_task.delay(request_id=self.id)

    def __empty_monitoring_object_fields(self):
        """
        Удаляет аттрибуты мониторинга из объекта заявки
        Нужно потому, что объекты списков, куда добавляются инстансы
        ответственных персон имеют одинаковые id в памяти
        в разных http-запросах
        """
        if not getattr(self, 'monitoring'):
            return
        if getattr(self.monitoring, 'persons_in_charge'):
            del self.monitoring.persons_in_charge
        if getattr(self.monitoring, 'messages'):
            del self.monitoring.messages
        del self.monitoring
        return self.reload()

    def _update_service_docs(self):
        if self.common_status == RequestStatus.ACCEPTED:
            return
        if self._created:
            return
        from processing.models.billing.storage import CompletionAct
        CompletionAct.objects(
            request=self.id,
            run=False,
        ).update(
            run=True,
        )

    def _denormalize_refs(self):
        if self._created:
            self._denormalize_tenant()
            self._denormalize_area()
            self._denormalize_provider()
            self._denormalize_house()
            self._denormalize_dispatcher()
        elif 'provider' in self._changed_fields:
            self._denormalize_provider()

    def notify_about_change(self, is_dirty_executors, new_document):
        """Отправка писем и СМС при изменении или сохранении заявки"""
        if not is_dirty_executors:
            return

        # подгрузка данных для письма
        provider = Provider.objects(id=self.provider.id).get()
        if self.dispatcher and self.dispatcher.id:
            dispatcher = Worker.objects(pk=self.dispatcher.id).first()
        else:
            dispatcher = None
        if self.tenant and self.tenant.id:
            tenant = Tenant.objects(pk=self.tenant.id).first()
        elif self.other_person and self.other_person.id:
            tenant = OtherTenant.objects(pk=self.other_person.id).first()
        elif self.other_person and self.other_person.str_name:
            tenant = self.other_person
            tenant.name_secured = 'иное лицо'
        else:
            tenant = None
        if not tenant:
            tenant = dispatcher
        # составление писем
        request_url = f'{provider.get_url()}/#/requests/detail/{self.id}'
        workers_map = dict(
            added='Вы назначены исполнителем',
            deleted='Вы удалены из исполнителей'
        )
        workers = dict(
            # добавленные сотрудники
            added=(
                self._get_added_workers()
                if not new_document
                else self.executors
            ),
            # удаленные сотрудники
            deleted=(
                self._get_deleted_workers()
                if not new_document
                else []
            )
        )
        workers_info = self._get_executors_accounts(workers)
        for type_, worker_list in workers.items():
            if not worker_list:
                continue

            # Сформируем тему сообщения и его тело
            theme, msg = self._get_theme_and_body_message(
                workers_map=workers_map,
                exc_type=type_
            )
            for worker in (x for x in workers_info if x['_id'] in worker_list):
                # Отправим письмо
                if worker.get('email'):
                    # Урл заявки получают только назначенные работники
                    url = request_url if type_ == 'added' else None
                    body = self._get_body_context(
                        provider,
                        worker,
                        tenant,
                        dispatcher,
                        theme,
                        url,
                    )
                    mail = TicketMail(
                        addresses=worker['email'],
                        subject=theme,
                        body=body,
                        provider_id=self.provider.id
                    )
                    mail.send()
                # Если указан мобильный, отправим СМС
                phone = next(
                    (x for x in worker['phones'] if x['type'] == 'cell'), None
                )
                if phone:
                    args = dict(
                        numbers=[f'7{phone["code"]}{phone["number"]}'],
                        subject='Обновление заявки',
                        text=msg,
                        datetime=datetime.datetime.now(),
                        provider=provider.id,
                    )
                    sms = SMSMessage(**args)
                    sms.save()
                    sms.send()

    def _get_body_context(self, provider, worker, tenant, dispatcher, theme,
                          url):
        """Генерация тела письма на основе шаблона"""
        context = dict(
            provider=provider,
            request=self,
            account=worker,
            tenant=tenant,
            dispatcher=dispatcher,
            title=theme,
            url=url
        )
        return self.TEMPLATE.render(context)

    def _get_added_workers(self):
        """Вспомогательный метод для получения добавленных работников"""
        return [
            x for x in self.executors
            if x not in self.old_state['executors']
        ]

    def _get_deleted_workers(self):
        """Вспомогательный метод для получения удаленных работников"""
        return [
            x for x in self.old_state['executors']
            if x not in self.executors
        ]

    def _get_executors_accounts(self, workers):
        """Подсасывание аккаунтов работников"""
        query = dict(id__in=workers['added'] + workers['deleted'])
        fields = 'id', 'email', 'phones'
        return tuple(Worker.objects(**query).only(*fields).as_pymongo())

    def _get_formatted_phone(self):
        """Форматирование телЕФОНА"""
        phones = self.tenant.phones
        return '\n'.join(
            f'+7 {phone.code} {phone.number}'
            for phone in phones if phone.number
        )

    def _get_theme_and_body_message(self, workers_map, exc_type):
        """Получение темы и сообщения уведомляющего письма"""
        r_type = 'домовой' if self.is_house_request else 'квартирной'
        theme = f'{workers_map[exc_type]} {r_type} заявки №{self.number}'
        if exc_type == 'added':
            if self.is_house_request:
                target = self.house.address
            else:
                target = (
                    f"{self.house.address}, "
                    f"{self.area.str_number}"
                    f"\nЖитель: {self.tenant.str_name}"
                    f"\n{self._get_formatted_phone()}"
                )
            msg = (
                f"Заявка №{self.number} "
                f"от {self.created_at.strftime('%d.%m.%Y')}\n"
                f"{target}\n"
                f"{self.body}"
            )
        else:
            msg = (
                f"Заявка №{self.old_state['number']} от "
                f"{self.old_state['created_at'].strftime('%d.%m.%Y')} отменена"
            )
        return theme, msg

    def delete(self, signal_kwargs=None, **write_concern):
        self.is_deleted = True
        from processing.models.billing.storage import CompletionAct
        from processing.models.billing.storage import StorageDocOut
        CompletionAct.objects(request=self.id).delete()
        StorageDocOut.objects(request=self.id).delete()
        return self.save(skip_notification=True)

    def _denormalize_tenant(self):
        """
        Denormalizes tenant, area and house fields in request
        :return: void
        """
        if self.tenant.id:
            tenant = Tenant.objects(pk=self.tenant.id).get()
            self.tenant.number = tenant.number
            self.tenant.str_name = tenant.str_name
            self.tenant.short_name = tenant.short_name
            self.tenant.phones = tenant.phones
            self.tenant.email = tenant.email
            self.tenant._type = tenant._type

    def _denormalize_area(self):
        if self.area.id:
            area = Area.objects(pk=self.area.id).get()
            self.area.number = area.number
            self.area.str_number = area.str_number
            self.area._type = area._type

    def _denormalize_house(self):
        house = House.objects(pk=self.house.id).get()
        self.house.address = house.address

    def _denormalize_provider(self):
        provider = Provider.objects(pk=self.provider.id).get()
        self.provider.str_name = provider.str_name

    def _denormalize_dispatcher(self):
        if self.dispatcher.id:
            dispatcher = Worker.objects(pk=self.dispatcher.id).get()
            self.dispatcher = RequestDispatcherDenormalized.from_ref(
                dispatcher)

    def validate_rating(self):
        if not self.rates:
            return
        if self.common_status != RequestStatus.PERFORMED:
            raise ValidationError('Only for "performed" status')
        elif 'HouseRequest' in self._type and not self.show_all:
            raise ValidationError('Only for public HouseRequests')

    def calculate_total_rate(self):
        """
        Calculates total_rate using rates list.
        :return: float
        """
        if len(self.rates) == 0:
            return None
        total_rate = sum(r.rate for r in self.rates)
        return total_rate / len(self.rates)

    def generate_unique_number(self, kladr_code='78', max_attempts=None):
        if not self.number:
            if max_attempts is None:
                max_attempts = settings.get('ACCOUNT_NUMBER_ATTEMPTS', 20)
            for _ in range(max_attempts):
                number = self._generate_number(kladr_code)
                if not Request.objects(number=number).as_pymongo().first():
                    self.number = number
                    return
            raise Exception(
                'Could not generate account number. Number of tries: {}'.format(
                    max_attempts))

    def _generate_number(self, kladr_code):
        account_number = kladr_code
        # Генерация 3 и 4 случайного разряда
        account_number += '{:02d}'.format(randint(0, 99))
        # Генерация 5 и 6 случайного разряда за исключением чисел 01 .. 12
        tmp_int = (randint(1, 87) + 13) % 100
        account_number += '{:02d}'.format(tmp_int)
        # Генерация разрядов 7 .. 13
        account_number += '{:07d}'.format(randint(0, 9999999))
        return account_number

    def _catch_changed_fields(self):
        if not self._created:
            history_fields = [
                (x, self.__to_dict(x))
                for x in self._get_changed_fields()
                if '.' not in x
            ]
            return history_fields

    def write_history(self, history_fields):
        """ Сохраним историю изменений документа """

        if not self.session_detail or not history_fields:
            return

        query = dict(ref_id=self.id, ref_model='Request')
        his_doc = History.objects(**query).first()
        if not his_doc:
            his_doc = History(ref_id=self.id, ref_model='Request')
            for hf, attr in history_fields:
                new_field = [dict(value=attr, **self.session_detail)]
                setattr(his_doc, hf, new_field)
        else:
            for hf, attr in history_fields:
                doc_attr = getattr(his_doc, hf, None)
                if doc_attr:
                    doc_attr.append(dict(value=attr, **self.session_detail))
                else:
                    setattr(
                        his_doc, hf, [dict(value=attr, **self.session_detail)]
                    )
        his_doc.save()

    def __to_dict(self, field):
        if '.' in field:
            field = field.split('.')[0]
        field = getattr(self, field)
        if isinstance(field, EmbeddedDocument):
            field = dict(field.to_mongo())
        return field

    def _denormalize_fast_kinds(self):
        """
        Денормализация быстрых заявок.
        Список ID из kinds используется как ключ для получения быстрого ID.
        """
        if self.kinds:
            fast_kinds = FAST_KINDS_REVERSED.get(tuple(sorted(self.kinds)))
            if fast_kinds:
                self.fast_kinds = fast_kinds

    @staticmethod
    def get_fast_kinds(kinds):
        """ Получение ID быстрых kinds, на основании полученных kinds """

        # Сортируем входящий список
        kinds = tuple(sorted(kinds))
        # Далее ищем полное и частичное совпадениея
        full_match = FAST_KINDS_REVERSED.get(kinds)
        fast_kinds = [full_match] if full_match else []
        for f_k, k in FAST_KINDS.items():
            # Если переданный список имеет полное вхождение своих элементов
            if all([x in k for x in kinds]):
                fast_kinds.append(f_k)
        return fast_kinds

    @classmethod
    def process_house_binds(cls, house_id):

        groups = get_house_groups(house_id)
        cls.objects(
            _type='HouseRequest',
            house__id=house_id,
        ).update(
            set___binds__hg=groups,
        )
        areas = Area.objects(house__id=house_id).only('id').as_pymongo()
        for area in areas:
            groups = get_area_house_groups(area['_id'], house_id)
            cls.objects(
                _type='AreaRequest',
                area__id=area['_id'],
            ).update(
                set___binds__hg=groups,
            )

    @classmethod
    def process_provider_binds(cls, provider_id, **kwargs):
        from processing.models.billing.business_type import BusinessType

        pushed = cls.objects(
            provider__id=provider_id,
        ).update(add_to_set___binds__pr=provider_id)
        # добавить себя в дома, где является udo
        b_type = BusinessType.objects(slug='udo').as_pymongo().first()
        houses_udo = get_binded_houses(provider_id, business_type=b_type['_id'])
        if houses_udo:
            pushed += cls.objects(
                provider__id__ne=provider_id,
                house__id__in=houses_udo,
            ).update(add_to_set___binds__pr=provider_id)
            pulled = cls.objects(
                provider__id__ne=provider_id,
                house__id__nin=houses_udo,
                _binds__pr=provider_id,
            ).update(pull___binds__pr=provider_id)
        else:
            pulled = cls.objects(
                provider__id__ne=provider_id,
                _binds__pr=provider_id,
            ).update(pull___binds__pr=provider_id)
        return pushed, pulled

    def _get_providers_binds(self):
        """
        Организация, выполняющая заявку, а также организация с типом udo на
        этом доме
        """
        result = {self.provider.id}
        house = House.objects(pk=self.house.id).get()
        udo_provider = house.get_provider_by_business_type('udo')
        if udo_provider:
            result.add(udo_provider)
        return list(result)

    def _get_house_binds(self):
        if self.area and not self._is_house_request:
            return get_area_house_groups(self.area.id, self.house.id)
        else:
            return get_house_groups(self.house.id)

    def _is_house_request(self):
        return 'HouseRequest' in self._type

    def update_users_tasks(self):
        """ 'Уведомление' о новой заявке"""
        update_users_journals.delay(self.house.id)

    def _copy_photos_from_ticket(self):
        """ Копирование вложенных файлов из обращения. """
        ticket = Ticket.objects(id=self.ticket).get()
        files = ticket.initial.files
        if files:
            description = ticket.initial.body
            self.photos = []
            for f in files:
                try:
                    file = get_file_from_gridfs(None, uuid=f.uuid, raw=True)
                except DoesNotExist:
                    continue
                file_id, _ = put_file_to_gridfs(
                    self.__class__.__name__,
                    self.provider.id,
                    file.read(),
                    filename=file.name,
                    content_type=file.content_type,
                )
                self.photos.append(
                    PhotoEmbedded(
                        description=description,
                        file=Files(file=file_id, name=file.name)
                    )
                )

    def _closed_with_created_ticket(self):
        """ Закрытие заявки после создания из нее обращения. """
        ticket = Ticket.objects(id=self.ticket).get().str_number
        self.common_status = RequestStatus.ABANDONMENT
        self.comment = f'На основании заявки №{self.number}' \
                       f' создано обращение №{ticket}'

    def notify_performed(self):
        send_request_notification.delay(request_id=self.id)

    def convert_status_to_setl(self):
        if (
                self.commercial_data.payable == RequestPayableType.PRE
                and self.common_status == RequestStatus.RUN
        ):
            if self.commercial_data.pay_status == RequestPayStatus.NOT_PAID:
                return SetlRequestStatus.WAIT_FOR_PAY
            elif self.commercial_data.pay_status != RequestPayStatus.PAID:
                return SetlRequestStatus.PAID
        return REQUEST_STATUS_SETL_HOME[self.common_status]

    def change_status_setl_home(self):
        from app.setl_home.models.request_setl_home import SetlHomeRequest
        setl_home = SetlHomeRequest.objects(
            number_request=self.number,
        ).first()
        if not setl_home:
            return
        from app.setl_home.task.post_data import post_setl_request_status
        setl_home.status = self.convert_status_to_setl()
        setl_home.save()
        post_setl_request_status.delay(self.pk)

    def _set_persons_in_charge(self) -> None:
        from app.requests.core.controllers.services import RequestService
        persons_ids = [
            e for e in
            {self.dispatcher.id, *self.executors}
            if e is not None
        ]
        RequestService(request=self).add_persons_in_charge(persons=persons_ids)

    def _mirror_executor_add_to_pic(self) -> None:
        from app.requests.core.controllers.services import RequestService
        new_executors = (
                set(self.executors) - set(self.old_state['executors'])
        )
        RequestService(request=self).add_persons_in_charge(
            persons=new_executors,
        )


class RequestKindBase(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'RequestKindBase',
    }
    slug = StringField(required=True)
    name = StringField(required=True)
    parents = ListField(ObjectIdField())
    default_child = ObjectIdField()
    service_type = ReferenceField('from processing.models.billing.ServiceType')
    name_active = StringField()

    _type = ListField(StringField())


class RequestSample(Document, BindedModelMixin):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'RequestSample',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('_binds.pr', 'title'),
        ],
    }
    provider = ObjectIdField()
    title = StringField()
    text = StringField()
    type = StringField(choices=REQUEST_SAMPLES_TYPES_CHOICES, default='body')
    kinds = ListField(
        ObjectIdField(verbose_name='Ссылка на RequestKind'),
        verbose_name='Динамический вид',
        null=True
    )
    common_status = StringField(
        choices=REQUEST_STATUS_CHOICES,
        verbose_name='Статус',
        null=True
    )
    _binds = EmbeddedDocumentField(
        ProviderBinds,
        verbose_name='Привязки к организации и группе домов (P)'
    )

    def save(self, *args, **kwargs):
        if not self._binds:
            self._binds = ProviderBinds(pr=self._get_providers_binds())
        self.restrict_changes()
        super().save(*args, **kwargs)

    @classmethod
    def process_provider_binds(cls, provider_id, **kwargs):
        pulled_query = dict(provider__ne=provider_id, _binds__pr=provider_id)
        pulled_updater = dict(pull___binds__pr=provider_id)
        pulled = cls.objects(**pulled_query).update(**pulled_updater)

        pushed_query = dict(provider=provider_id)
        pushed_updater = dict(add_to_set___binds__pr=provider_id)
        pushed = cls.objects(**pushed_query).update(**pushed_updater)
        return pushed, pulled


class RequestBlank(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'RequestBlank'
    }
    name = StringField()
    is_default = BooleanField()
    file = EmbeddedDocumentField(Files, verbose_name='HTML-шаблон')


class RequestLogs(Document):
    """
    Модель для логов заявок.
    """
    meta = {
        'db_alias': 'logs-db',
        'collection': 'RequestLogs',
        'indexes': ['created'],
    }

    created = DateField(
        verbose_name='Дата создания', default=datetime.date.today)
    request_id = ObjectIdField(verbose_name='Id заявки')
    status = BooleanField(verbose_name='Выполнена ли.')
    description = StringField(verbose_name='Описание', null=True)


class AlarmEmail(EmbeddedDocument):
    email = EmailField()
    executor_name = StringField()


class KindsToExecutorBinds(EmbeddedDocument):
    kind = ObjectIdField(verbose_name='Id Категории/Подкатегории')
    workers = ListField(
        ObjectIdField(),
        verbose_name='Id исполнителей ответственных за данную категорию'
    )
    description = StringField(verbose_name='Описание Категории/Подкатегории')
    alarm_emails = EmbeddedDocumentListField(
        AlarmEmail,
        verbose_name='Почта для срочного оповещения'
    )


class RequestAutoSelectExecutorBinds(Document):
    """
    Модель в которой записывается связь Категория - Исполнитель
    для автоматического назначения исполнителя на заявку
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'RequestAutoSelectExecutorBinds',
        'indexes': ['provider']
    }

    provider = ObjectIdField(verbose_name='Id провайдера')
    kinds_executor = EmbeddedDocumentListField(
        KindsToExecutorBinds,
        verbose_name='Привязка Категория - Исполнители'
    )