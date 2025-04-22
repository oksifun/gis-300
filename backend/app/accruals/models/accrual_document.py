import datetime

from mongoengine import Document, EmbeddedDocument, StringField, \
    DateTimeField, EmbeddedDocumentField, \
    EmbeddedDocumentListField, ObjectIdField, DynamicField, BooleanField, \
    ValidationError, FloatField, ListField, IntField

from app.c300.core.delete_data import soft_delete_by_queryset
from lib.dates import start_of_month
from processing.models.billing.accrual import Accrual
from processing.models.billing.base import ProviderHouseGroupBinds, \
    BindedModelMixin
from processing.models.billing.common_methods import get_house_groups
from processing.models.billing.embeddeds.base import DenormalizedEmbeddedMixin
from processing.models.billing.files import Files
from processing.models.choices import *
from processing.models.exceptions import CustomValidationError


class ServiceSettings(EmbeddedDocument):
    service = ObjectIdField(required=True, verbose_name='Услуга')
    vendor = ObjectIdField(null=True, verbose_name='Поставщик услуги')
    contract = ObjectIdField(null=True, verbose_name='ID договора')


class AccrualPenaltySettingsEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    include_penalty = BooleanField()  # TODO описание
    debt_penalty_date = DateTimeField(
        required=True,
        verbose_name='Дата старейшего долга для пени, '
                     'дата предыдущего учёта пени',
    )
    include_subsidy = BooleanField(null=True)  # TODO описание
    penalty_till = DateTimeField(
        required=True,
        verbose_name='Дата, на которую считать пени',
    )
    bill_announce = StringField(null=True)  # TODO описание
    services = EmbeddedDocumentListField(
        ServiceSettings,
        verbose_name='Настройки по услугам',
    )
    old_period_penalty_refund = BooleanField(
        default=False,
        verbose_name='Проверять на необходимость возврата пеней '
                     'старых периодов',
    )


class AccrualDocTotalEmbedded(EmbeddedDocument):
    """
    Объекты суммирования
    """
    id = ObjectIdField(db_field="_id")
    value = FloatField(verbose_name='Значение')
    formula_code = StringField(verbose_name='Системный код')
    title = StringField(verbose_name='Наименование')
    tariff_plans = ListField(
        ObjectIdField(),
        verbose_name='В каких тарифных планах присутствует',
    )
    sum_docs = BooleanField(verbose_name='Суммировано из других документов')
    house_group = ObjectIdField(verbose_name='Группа домов')


class CalcLog(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    code = DynamicField()
    comment = DynamicField()
    type = DynamicField()


class SectorBind(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    sector_code = StringField()  # TODO описание
    provider = ObjectIdField()
    settings = EmbeddedDocumentField(AccrualPenaltySettingsEmbedded)


class LockStatus(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")


class ReceiptFiles(EmbeddedDocument):
    sector_code = StringField()
    file = EmbeddedDocumentField(Files)


class CacheService(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")

    cold_water = IntField(verbose_name="ХВС индивидуальное")
    cold_water_public = IntField(verbose_name="ХВС общедомовое")
    waste_water = IntField(verbose_name="Водоотведение")
    hot_water = IntField(verbose_name="ГВС индивидуальное")
    hot_water_public = IntField(verbose_name="ГВС общедомовое")
    heat = IntField(verbose_name="Отопление")
    electricity = IntField(verbose_name="Электроснабжение индивидуальное")
    electricity_public = IntField(verbose_name="Электроснабжение общедомовое")
    gas = IntField(verbose_name="Газ")
    communal_other_services = IntField(
        verbose_name="Остальные услуги в группе коммунальных",
    )
    communal = IntField(verbose_name="Все услуги в группе коммунальных")

    housing = IntField(verbose_name="Все услуги в группе жилищных")
    capital_repair = IntField(verbose_name="Взносы на капитальный ремонт")
    other = IntField(verbose_name="Все услуги в группе прочие")
    heat_water_other = IntField()
    penalties = IntField(verbose_name="Пени")


class SentRegisters(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    date = DateTimeField(verbose_name='Дата отправки реестра')
    file = EmbeddedDocumentField(Files, verbose_name='Файл в гридфс')


class AccrualDocEmbeddedHouse(DenormalizedEmbeddedMixin, EmbeddedDocument):

    id = ObjectIdField(db_field="_id")
    address = StringField(
        verbose_name="Адрес дома, на жителей которого расчитаны начисления",
    )
    fias_addrobjs = ListField(
        StringField(),
        verbose_name='Родительские addrobj',
    )


class NotificationsStatusEmbedded(EmbeddedDocument):
    state = StringField(required=True, default='ready')
    when_sent = DateTimeField(required=False)


class PublicCommunalRecalculationTariffEmbedded(EmbeddedDocument):
    area_type = StringField()
    service_code = StringField()
    tariff = IntField()


class PublicCommunalRecalculationEmbedded(EmbeddedDocument):
    resource = StringField(
        verbose_name='Тип коммунального ресурса',
    )
    month = DateTimeField(
        verbose_name='Месяц',
    )
    value_calculated = IntField(
        verbose_name='Сумма рассчитанная',
    )
    value_included = IntField(
        verbose_name='Сумма начисленная',
    )
    value = IntField(
        verbose_name='Сумма к перерасчёту (рассчитано минус начислено)',
    )
    consumption_calculated = FloatField(
        verbose_name='Расход рассчитанный',
    )
    consumption_included = FloatField(
        verbose_name='Расход начисленный',
    )
    consumption = FloatField(
        verbose_name='Расход к перерасчёту (рассчитано минус начислено)',
    )
    included = BooleanField(
        default=False,
        verbose_name='Было распределено в текущем документе',
    )
    tariffs = EmbeddedDocumentListField(
        PublicCommunalRecalculationTariffEmbedded,
        verbose_name='Использованные тарифы в зависимости от типов помещений',
    )


class AccrualDoc(BindedModelMixin, Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'AccrualDoc',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            '_binds.hg',
            '_binds.pr',
        ],
    }
    # legacy - 'type': Required(DocType)
    document_type = StringField(
        required=True,
        choices=ACCRUAL_DOCUMENT_TYPE_CHOICES,
        verbose_name="Тип документа",
        db_field='type',
    )
    date = DateTimeField(required=True, verbose_name="Дата документа")

    # legacy - Denormalized('House', ['address'])
    house = EmbeddedDocumentField(
        AccrualDocEmbeddedHouse,
        verbose_name='Информация о доме',
    )
    # legacy - Ref('Provider')
    provider = ObjectIdField(
        verbose_name="Организация-владелец документа",
    )

    settings = EmbeddedDocumentField(AccrualPenaltySettingsEmbedded)
    date_from = DateTimeField(
        required=True,
        verbose_name="Начало периода, на который рассчитаны начисления",
    )
    date_till = DateTimeField(
        required=True,
        verbose_name="Конец периода, на который рассчитаны начисления",
    )
    payers_count = IntField(
        verbose_name='Количество плательщиков по документу начислений'
    )
    tariff_plan = ObjectIdField(
        verbose_name='Тарифный план по умолчанию для документа',
    )
    description = StringField(verbose_name="Описание")
    archive = ListField()
    # legacy - [SectorBind]
    sector_binds = EmbeddedDocumentListField(SectorBind)
    pay_till = DateTimeField(verbose_name="Оплатить до", null=True)

    # legacy - Required(Status, default=Status.DEFAULT)
    status = StringField(
        required=True,
        choices=ACCRUAL_DOCUMENT_STATUS_CHOICES,
        default=AccrualDocumentStatus.WORK_IN_PROGRESS,
        verbose_name="Статус документа"
    )
    # legacy - [Total]
    totals = EmbeddedDocumentListField(AccrualDocTotalEmbedded)

    # legacy - LockStatus
    lock = EmbeddedDocumentField(LockStatus)

    # legacy - [CalcLog]
    logs = EmbeddedDocumentListField(CalcLog)

    cache_services = EmbeddedDocumentField(CacheService)
    caching_wip = BooleanField(default=False)

    sent_registries = EmbeddedDocumentField(SentRegisters)

    receipt_files = EmbeddedDocumentListField(
        ReceiptFiles,
        verbose_name='Словарь файлов квитанций по направлениям'
    )
    is_deleted = BooleanField()
    disable_in_cabinet = BooleanField(
        verbose_name="Разрешение распечатки квитанции",
        default=False,
    )
    solvent = BooleanField(
        default=False,
        verbose_name='Можно ли запускать автоплатеж и рассылку'
    )
    exempt_from_mailing = BooleanField(
        default=False,
        verbose_name='Можно ли запускать рассылку'
    )
    notifications = EmbeddedDocumentField(
        NotificationsStatusEmbedded,
        verbose_name='Информация о рассылке уведомлений'
    )
    public_communal_recalculations = EmbeddedDocumentListField(
        PublicCommunalRecalculationEmbedded,
        verbose_name='Перерасчёты по коммунальным услугам ОДН',
    )

    _binds = EmbeddedDocumentField(
        ProviderHouseGroupBinds,
        verbose_name='Привязки к группе домов и провайдеру'
    )

    CHANGEABLE_LOCK_FIELDS = {
        'status',
        'description',
        'disable_in_cabinet',
        'receipt_files',
        'sent_registries',
        'cache_services',
        'totals',
        'solvent',
    }

    @property
    def actual_count(self) -> int:
        """Количество (действительных) начислений в документе"""
        return Accrual.objects(doc__id=self.id, is_deleted__ne=True).count()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.doc_before_save = (
            dict(self.to_mongo())
            if not self._created
            else None
        )

    def save(self, is_copy=False, *args, **kwargs):
        """
        Сохранение документа
        """
        send_registries = kwargs.pop('send_registries', False)
        ignore_validation = kwargs.pop('ignore_validation', False)
        print_receipt = kwargs.pop('print_receipt', False)
        if self._created:
            self.notifications = NotificationsStatusEmbedded()
            self._denormalize_house()
        if (not self._created and not is_copy) and not print_receipt:
            # проверки разрешённых изменений существующего документа
            self.check_for_lock()
            # Если меняли тип документа
            if not ignore_validation and self.doc_before_save:
                self.validate_status_change()
            if self._is_key_dirty('type'):
                self.validate_type_change()
        if not self._binds:
            # расчёт привязок
            self._binds = ProviderHouseGroupBinds(
                pr=self._get_providers_binds(),
                hg=self._get_house_binds(),
            )
        # проверка на запрещённые изменения
        self.restrict_changes()
        # сохранение
        if not self._created or is_copy:
            changed_fields = self._changed_fields
            self.denormalize_settings_services()
        else:
            changed_fields = []

        result = super().save(*args, **kwargs)

        # денормализация данных в зависимые документы
        self.denormalize_accruals(changed_fields)

        # постановка задач на офсеты
        if not ignore_validation and self.doc_before_save:
            self.run_after_tasks(send_registries=send_registries)

        # ставим в (отдельную от изменений) очередь на выгрузку в ГИС ЖКХ
        if self.status == AccrualDocumentStatus.READY:
            from app.gis.models.gis_queued import GisQueued
            GisQueued.put(self, hours=4)

        return result

    def _denormalize_house(self):
        from app.house.models.house import House
        house = House.objects(pk=self.house.id).get()
        self.house = AccrualDocEmbeddedHouse.from_ref(house)

    @classmethod
    def get_period_meters(cls, house, provider, house_meters=False,
                          readings_stat=False):
        """
        Получить последний документ начислений и area_meters_month_get по дому
        """
        from processing.models.billing.settings import ProviderAccrualSettings

        statuses = ['ready', 'edit']
        if readings_stat:
            statuses.append('wip')
        accrual_docs = cls.objects(
            house__id=house,
            status__in=statuses,
        ).order_by(
            '-date_from',
        )[:1]
        doc = accrual_docs[0] if accrual_docs else None

        query = dict(house=house, provider=provider)
        settings = ProviderAccrualSettings.objects(**query).first()
        if not settings:
            raise ValidationError(
                "Для указаного дома не найдено настроек начислений"
            )
        month_get = (
            settings.house_meters_month_get
            if house_meters
            else settings.area_meters_month_get
        )
        return doc, month_get, settings.area_meters_month_get_usage

    @classmethod
    def get_nearest_document_date(cls, date_on, provider_id, house_id):
        docs = cls.objects(
            __raw__={
                'provider': provider_id,
                'house._id': house_id,
                'date': {'$lt': date_on},
                'type': AccrualDocumentType.MAIN,
            },
        ).only(
            'date',
        ).order_by(
            '-date',
        ).as_pymongo()
        docs = list(docs[0: 1])
        if len(docs) > 0:
            return docs[0]['date']
        else:
            return datetime.datetime(2000, 1, 1, 0, 0, 0, 0)

    def denormalize_settings_services(self):
        # TODO Можно оптимизировать денормализацию обновляю только те Accruals
        #  настройки которых изменились, что можно узнать по индексу
        #  self._get_changed_fields() -> ['sector_binds.0.settings.services']
        if self._is_triggers(['settings.services']):
            # TODO По хорошему нужно перенсти в after save,
            #  но так как это не сделано провалидируем модель
            #  перед денормализацией
            self.validate()
            services = self._get_grouped_services_by_sector()
            accruals = self._get_grouped_accruals_by_sector(list(services))

            for sector, sector_services in services.items():
                sector_accruals = accruals.get(sector)
                if not sector_accruals:
                    continue

                services_vendors = {x['service']: x for x in sector_services}
                for accrual in sector_accruals:
                    is_success = self._set_vendor_to_accrual(
                        accrual=accrual,
                        services_vendors=services_vendors
                    )
                    if is_success:
                        continue

    @staticmethod
    def _set_vendor_to_accrual(accrual, services_vendors):
        for a_service in accrual.services:
            vendor = services_vendors.get(a_service.service_type)
            if vendor and a_service.vendor:
                a_service.vendor.id = vendor['vendor']
                a_service.vendor.contract = vendor['contract']
                accrual.save()
                return True

        return False

    def _get_grouped_services_by_sector(self):
        services = [
            dict(sector=bind.sector_code, **dict(service.to_mongo()))
            for bind in self.sector_binds
            for service in bind.settings.services
        ]
        grouped_services_by_sector = {}
        for service in services:
            group = grouped_services_by_sector.setdefault(
                service['sector'], []
            )
            group.append(service)

        return grouped_services_by_sector

    def _get_grouped_accruals_by_sector(self, sectors):
        accruals = Accrual.objects(
            doc__id=self.id,
            sector_code__in=sectors
        )
        grouped_accruals_by_sector = {}
        for accrual in accruals:
            group = grouped_accruals_by_sector.setdefault(
                accrual['sector_code'], []
            )
            group.append(accrual)

        return grouped_accruals_by_sector

    def check_for_lock(self):
        has_locked_accruals = self.has_locked_accruals()
        if not has_locked_accruals:
            return False
        if set(self._changed_fields) - self.CHANGEABLE_LOCK_FIELDS:
            raise ValidationError('Document is locked')
        if self.status == 'wip' and self.doc_before_save['status'] != 'wip':
            raise ValidationError('Document is locked')

    def delete(self, signal_kwargs=None, **write_concern):
        if self.status != 'wip':
            raise CustomValidationError(
                'Разрешено только для документов в статусе редактирования',
            )
        if self.has_locked_accruals():
            raise CustomValidationError('Документ блокирован')
        accruals_qs = Accrual.objects(doc__id=self.id)
        soft_delete_by_queryset(accruals_qs, 'Accrual')
        super().delete(signal_kwargs, **write_concern)

    def _get_providers_binds(self):
        owners = {b.provider for b in self.sector_binds}
        if self.provider:
            owners.add(self.provider)
        return list(owners)

    def _get_house_binds(self):
        return get_house_groups(self.house.id)

    def get_account_ids(self) -> list:
        """Идентификаторы ЛС документа начислений"""
        return Accrual.objects(__raw__={  # начисления
            'doc._id': self.id,  # текущего документа
            'is_deleted': {'$ne': True},  # кроме удаленных
        }).distinct('account._id')  # : TenantId,...

    @classmethod
    def process_house_binds(cls, house_id):
        groups = get_house_groups(house_id)
        cls.objects(house__id=house_id).update(set___binds__hg=groups)

    @classmethod
    def process_provider_binds(cls, provider_id, **kwargs):
        pulled = cls.objects(
            provider__ne=provider_id,
            _binds__pr=provider_id,
        ).update(pull___binds__pr=provider_id)
        pushed = cls.objects(__raw__={'$or': [
            {'provider': provider_id},
            {'sector_binds.provider': provider_id},
        ]}).update(add_to_set___binds__pr=provider_id)
        return pushed, pulled

    def validate_status_change(self):
        new_status = self.status
        old_status = self.doc_before_save['status']
        # Авансовый отчет должен быть в статусе wip
        if self.document_type == 'adv':
            if old_status != 'wip':
                raise ValidationError('Авансовый отчет не в работе')
        # Смена статуса на wip только последнего документа
        # (кроме корректировочного - adj)
        if new_status == 'wip' and old_status != 'wip':
            if self.document_type != 'adj':
                # Последний по дате документ организации
                last_date_doc = AccrualDoc.objects(
                    provider=self.provider,
                    house__id=self.house.id,
                    status__ne='wip',
                ).order_by(
                    '-date_from',
                ).first().date_from
                if self.date_from != last_date_doc:
                    raise ValidationError('Не последний платежный документ')
        # Единственная неразрешенная смена статуса: wip -> edit
        if old_status == 'wip' and new_status == 'edit':
            raise ValidationError('Такая смена статуса не разрешена')

    def validate_type_change(self):
        check_condition = (
                self.document_type == 'main'
                and self.doc_before_save['type'] != 'main'
        )
        if check_condition:
            query = {
                'type': 'main',
                'provider': self.provider,
                'date_from': self.date_from,
                'house._id': self.house.id
            }
            a_docs = AccrualDoc.objects(__raw__=query).distinct('id')
            query = dict(doc__id__in=a_docs + [self.id])
            fields = 'owner', 'sector_code', 'account.id'
            accruals = tuple(
                Accrual.objects(**query).only(*fields).as_pymongo()
            )
            acc_repeats = {}
            for accrual in accruals:
                key = (
                    accrual['owner'],
                    accrual['sector_code'],
                    accrual['account']['_id']
                )
                group = acc_repeats.setdefault(key, dict(counter=0))
                group['counter'] += 1
                if group['counter'] > 1:
                    raise ValidationError('Основной документ уже существует')

    def has_locked_accruals(self):
        accruals = Accrual.objects(doc__id=self.id).as_pymongo().only('lock')
        for a in accruals:
            if a.get('lock'):
                return True
        return False

    def denormalize_accruals(self, changed_fields):
        update_keys = set(changed_fields) & {'date', 'pay_till', 'status'}
        if update_keys:
            Accrual.objects(
                doc__id=self.pk,
            ).update(
                **{f'doc__{k}': getattr(self, k) for k in update_keys},
            )

    def run_after_tasks(self, send_registries=False):
        accruals = Accrual.objects(doc__id=self.pk)
        accounts = accruals.distinct('account.id')
        # Новые значения полей
        new_date = self.date
        new_status = self.status
        old_status = self.doc_before_save['status']
        old_date = self.doc_before_save['date']
        sectors = [s_b.sector_code for s_b in self.sector_binds]
        # Если статус не менялся и он 'ready', а 'date' поменялось
        if all((
                new_status == old_status,
                old_status == 'ready',
                new_date != old_date
        )):
            # Расчет офсетов
            self._run_status_changed_tasks(accounts, sectors, old_date)
            # Рассчет кэша
            self._update_cache()
        # Если статус сменился на 'wip'
        elif new_status == 'wip' and old_status != new_status:
            # Обнуление поля bill в Accruals
            accruals.update(bill=None)
            # Расчет офсетов
            self._run_status_changed_tasks(accounts, sectors, old_date)
            # Рассчет кэша
            self._update_cache()
        # Если статус wip -> edit, ready
        elif old_status == 'wip' and new_status in ('edit', 'ready'):
            from app.accruals.cipca.tasks.create_tasks import create_run_task
            create_run_task(
                author_id=None,
                doc_id=self.pk,
                send_registries=send_registries,
                run_autopay_notify=getattr(self, 'run_autopay_notify', False),
            )
            # Расчет офсетов
            self._run_status_changed_tasks(accounts, sectors, old_date)
            # Рассчет кэша
            self._update_cache()

    def _update_cache(self):
        from app.caching.tasks.cache_update import \
            update_house_accruals_cache
        for sector_bind in self.sector_binds:
            update_house_accruals_cache.delay(
                provider_id=sector_bind.provider,
                house_id=self.house.id,
                month=self.date_from.replace(day=1, hour=0, minute=0, second=0),
                sector=sector_bind.sector_code,
            )

    def _run_status_changed_tasks(self, account_ids, sector_codes, old_date):
        self.update_services_cache(old_date)

    def update_services_cache(self, old_date):
        from app.accruals.tasks.cache.house_service import \
            init_house_service_cache_update
        providers = {bind.provider for bind in self.sector_binds}
        period = start_of_month(min(self.date_from, self.date, old_date))
        for provider in providers:
            init_house_service_cache_update(
                self.house.id,
                period,
                provider_id=provider,
            )

    @classmethod
    def last_period_of(cls, provider_id):
        """Получить последний закрытый период организации"""
        last_accrual_doc = cls.objects(
            provider=provider_id, document_type='main',
            status=AccrualDocumentStatus.READY
        ).only('date_from').as_pymongo().order_by('-date').first()

        return last_accrual_doc['date_from']


class SentAccrualDoc(EmbeddedDocument):
    doc_id = ObjectIdField(verbose_name='ИД документа')
    sent = BooleanField(verbose_name='Отправлен ли')


class AccrualDocDailySendReport(Document):
    accrual_documents = EmbeddedDocumentListField(SentAccrualDoc)
    day = DateTimeField(required=True)

    meta = {
        'db_alias': 'queue-db',
        'collection': 'accrual_doc_daily_send_report',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'day',
        ],
    }
