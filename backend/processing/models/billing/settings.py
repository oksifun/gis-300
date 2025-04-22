import datetime

from bson import ObjectId
from mongoengine import ObjectIdField, IntField, EmbeddedDocumentListField, \
    DictField, ValidationError
from mongoengine.document import Document, EmbeddedDocument
from mongoengine.fields import StringField, ListField, BooleanField, \
    EmbeddedDocumentField, DateTimeField

from processing.models.billing.tariff_plan import TariffPlan
from processing.models.billing.base import CustomQueryMixin
from processing.models.billing.documents_template import ReceiptTemplate
from processing.models.choices import GENERAL_VALUE_TYPE_CHOICES, \
    GeneralValueType, ACCRUAL_SECTOR_TYPE_CHOICES, MONTH_TYPE_CHOICES, \
    MonthType, AREA_TYPE_CHOICES, AreaType, \
    PUBLIC_COMMUNAL_SERVICES_RECALC_TYPE_CHOICES, \
    PublicCommunalServicesRecalcType

PRIVILEGE_TYPES = (
    ('regional', 'региональные'),
    ('federal', 'федеральные'),
    ('general', 'общие')
)

MAIN_TYPE = (
    ('Payments', 'Оплаты'),
    ('Commission', 'Комиссия'),
)


class PenaltyChangeCondition:
    PAID = 'paid'
    DEBT = 'debt'
    EXPIRE = 'expire'


CONDITION_CHANGE_CHOICES = (
    (PenaltyChangeCondition.PAID, 'по дате погашения начиная с'),
    (PenaltyChangeCondition.DEBT, 'по периоду задолженности с'),
    (PenaltyChangeCondition.EXPIRE, 'по дате просрочки с')
)


class PenaltyOverdueType:
    ACCRUED = 'accrued'
    INFORMATION = 'information'


PENALTY_OVERDUE_TYPES_CHOICES = (
    (PenaltyOverdueType.ACCRUED, 'Начислено'),
    (PenaltyOverdueType.INFORMATION, 'Информационно'),
)
PENALTIES_TRACKER = (
    ('monthly', 'начислять помесячно'),
    ('after_payment', 'начислять после оплат'),
    ('do_not_calculate', 'не считать пени'),
)
COLUMNS = (
    ('location', 'Название города'),
    ('street', 'Название улицы'),
    ('house_number', 'Номер дома'),
    ('house_bulk', 'Корпус дома'),
    ('area_number', 'Номер квартиры'),
    ('first_name', 'Имя'),
    ('last_name', 'Фамилия'),
    ('patronimic_name', 'Отчество'),
    ('short_name', 'Фамилия И.О.'),
    ('str_name', 'Фамилия Имя Отчество'),
    ('kodpol', 'Внутренный id льготника'),
    ('kod_kat', 'Категория льготы'),
    ('square_integer', 'Площадь помещения (целая часть)'),
    ('tenants_family', 'Кол.человек льгот на семью'),
    ('tenants_privileged', 'Кол.человек льгот на льготника'),

    ('value_housing', 'Сумма льготы на жилищные услуги'),
    ('recalculation_housing', 'Сумма перерасчёта льготы на жилищные услуги'),
    ('allow_housing', 'Дано ли право на льготу на жилищные услуги'),

    ('value_cws', 'Сумма льготы на ХВС'),
    ('recalculation_cws', 'Сумма перерасчёта льготы на ХВС'),
    ('allow_cws', 'Дано ли право на льготу на ХВС'),

    ('value_ww', 'Сумма льготы на водоотведение'),
    ('recalculation_ww', 'Сумма перерасчёта льготы на водоотведение'),
    ('allow_ww', 'Дано ли право на льготу на водоотведение'),

    ('value_garbage', 'Сумма льготы на вывоз мусора'),
    ('recalculation_garbage', 'Сумма перерасчёта льготы на вывоз мусора'),
    ('allow_garbage', 'Дано ли право на льготу на вывоз мусора'),

    ('value_gas', 'Сумма льготы на газ'),
    ('recalculation_gas', 'Сумма перерасчёта льготы на газ'),
    ('allow_gas', 'Дано ли право на льготу на газ'),

    ('value_electricity', 'Сумма льготы на эл/энергию'),
    ('recalculation_electricity', 'Сумма перерасчёта льготы на эл/энергию'),
    ('allow_electricity', 'Дано ли право на льготу на эл/энергию'),

    ('value_heat', 'Сумма льготы на теплоснабжение'),
    ('recalculation_heat', 'Сумма перерасчёта льготы на теплоснабжение'),
    ('allow_heat', 'Дано ли право на льготу на теплоснабжение'),
)


ENCODINGS = 'cp866', 'utf8', 'cp1251', 'koi8r', 'ascii', 'iso-8859-5'

EXTENSIONS = 'dbf', 'xlsx', 'xls', 'csv'


class TemplateSettings(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    # Required(Ref('ReceiptTemplate'))
    template = ObjectIdField(required=True)
    # Объявление на квитанции
    # ReceiptInfoBlock
    info_blocks = DictField()
    # Дата начала действия
    date_from = DateTimeField()


class AreaTypeAccrualSettings(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")

    template = ListField(EmbeddedDocumentField(TemplateSettings))

    # Размер шрифта на квитанции
    # Поле не используется
    font_size = IntField(min_value=7, max_value=14, null=True)

    # Required(Type, default=Type.LivingArea),
    type = StringField(
        required=True,
        choices=AREA_TYPE_CHOICES,
        default=AreaType.LIVING_AREA
    )

    # Код услуги «Город», прикрепленный к используемому р/с
    service_code = StringField(null=True)

    # Расчетный счет
    # Any(None, BankAccountNumber)
    # where BankAccountNumber = lambda x: str(x).replace(' ', '') wtf?
    bank_account = StringField(null=True)


class ExpirationRatesEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    days_from = IntField(default=1, required=True)
    days_till = IntField(null=True, default=None)
    share_rate = ListField(IntField(), default=[1, 300], required=True)


class GracePeriod(EmbeddedDocument):
    date_from = DateTimeField(
        default=None,
        null=True,
        blank=True,
        verbose_name='дата начала льготного периода'
    )
    date_till = DateTimeField(
        default=None,
        null=True,
        blank=True,
        verbose_name='дата конца льготного периода'
    )


class ConditionsEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    date = DateTimeField()
    value = StringField(
        verbose_name='условия использования изменений',
        required=True,
        default='debt',
        choices=CONDITION_CHANGE_CHOICES
    )
    expiration_rates = EmbeddedDocumentListField(
        ExpirationRatesEmbedded,
        required=True,
        verbose_name='ставки по дням просрочки',
        default=lambda: [ExpirationRatesEmbedded()]
    )


class PenniesEmbedded(EmbeddedDocument):
    date = IntField(verbose_name='день начисления пени')
    tracking = StringField(
        verbose_name='учитывать пени как ...',
        default='do_not_calculate',
        choices=PENALTIES_TRACKER
    )
    month_offset = IntField(
        verbose_name='месяц начисления пени '
                     '(1 — следующий, 2 — через один и т.д.)'
    )
    jsk_prof_charge_date = DateTimeField(
        verbose_name='Дата посл. начисления пени в ЖСК-Проф'
    )
    grace_period = EmbeddedDocumentListField(
        GracePeriod,
        verbose_name='период в которым не считаются дни для пени',
    )
    conditions = EmbeddedDocumentListField(
        ConditionsEmbedded,
        verbose_name='условия использования пеней',
    )


class SectorSettings(EmbeddedDocument):
    id = ObjectIdField(db_field="_id", default=ObjectId)

    # [AreaTypeAccrualSettings]
    area_types = ListField(EmbeddedDocumentField(AreaTypeAccrualSettings))
    # Тарифный план по умолчанию
    # Ref(TariffPlanDoc)
    tariff_plan = ObjectIdField(null=True)

    # Код направления
    sector_code = StringField(choices=ACCRUAL_SECTOR_TYPE_CHOICES)

    # Код услуги «Город», прикрепленный к используемому р/с
    # String
    service_code = StringField(null=True)

    # Используемый на этом направлении р/с
    # BankAccountNumber
    bank_account = StringField(null=True)
    other_bank_accounts = ListField(
        StringField(),
        verbose_name='Рассчетные счета других банков',
        default=[],
        null=True,
    )

    # Включать долги в начисления
    # Required(Boolean, default=False)
    include_debt = BooleanField(required=True, default=False)

    # Получать показания счётчиков через банк, если True то
    # Required(Boolean, default=False)
    registry_meters = BooleanField(required=True)

    # счетчиков в реестре для банка быть не должно, если
    # False то реестр в банк строится со счётчиками
    # настройки пеней  # TODO
    # Required(Pennies, default=Pennies())
    pennies = EmbeddedDocumentField(PenniesEmbedded)

    def get_sector_by_area_type(self, area_type):
        """
        Получение настроек по коду направления и типу помещения
        """
        area_settings = [x for x in self.area_types if x.type == area_type]

        if not area_settings:
            return None

        return area_settings[0]


class GeneralValues(EmbeddedDocument):
    # тип настройки
    type = StringField(
        required=True,
        choices=GENERAL_VALUE_TYPE_CHOICES,
        default=GeneralValueType.MANUAL_OPERATION
    )

    # справочник дебета
    subconto_dt = ListField(StringField(), required=True, default=[''])

    # справочник кредита
    subconto_ct = ListField(StringField(), required=True, default=[''])

    # счет дебета
    debt_number = StringField(required=True, default='')

    # счет кредита
    credit_number = StringField(required=True, default='')


class HouseValues(EmbeddedDocument):
    # тип помещений
    areas_type = StringField(choices=AREA_TYPE_CHOICES,
                             default=AreaType.ALL)
    # ссылка на дом
    # Ref('House')
    house = ObjectIdField()


class EmbeddedBindings(EmbeddedDocument):

    db_name = StringField(
        choices=COLUMNS,
        verbose_name='Название столбца в системе'
    )
    col_name = StringField(verbose_name='Название столбца в файле')
    default = StringField(verbose_name='Значение по умолчанию')
    formula = StringField(verbose_name='Формула для расчета')


class PrivilegeFileEmbedded(EmbeddedDocument):
    coding = StringField(choices=ENCODINGS)
    extension = StringField(choices=EXTENSIONS)
    bindings = EmbeddedDocumentField(EmbeddedBindings)
    privilege_type = StringField(choices=PRIVILEGE_TYPES)
    password = StringField()
    zip_package = BooleanField(default=False)


class BaseSettings(CustomQueryMixin):
    _type = ListField(
        StringField(required=True),
        default=[
            "AccrualSettings",
            "ProviderAccrualSettings",
            "ProviderSettings"
        ]
    )
    provider = ObjectIdField(
        required=True,
        verbose_name='Организация-владлец настроек'
    )
    sectors = ListField(
        EmbeddedDocumentField(SectorSettings),
        verbose_name='Реквизиты, используемые на разных направлениях'
    )
    bank_number = StringField(null=True)

    def save(self, *args, **kwargs):
        if self.bank_number:
            self.bank_number = self.bank_number.replace(' ', '')
        return getattr(super(), 'save')(*args, **kwargs)


class ProviderAccrualSettingsMixin(BaseSettings):
    house = ObjectIdField(null=True, verbose_name='Привязка к дому')
    area_meters_month_get = IntField(
        choices=MONTH_TYPE_CHOICES,
        default=MonthType.CURRENT,
        verbose_name='месяц учета показаний квартирных счетчиков'
    )
    area_meters_month_get_usage = BooleanField(
        default=True,
        verbose_name='использовать ли настройку area_meters_month_get'
    )
    house_meters_month_get = IntField(
        choices=MONTH_TYPE_CHOICES,
        default=MonthType.CURRENT,
        verbose_name='месяц учета показаний домовых счетчиков'
    )
    house_meters_formula = StringField(
        null=True,
        verbose_name='Формула вывода домовых счетчиков'
    )
    show_house_meters_formula = BooleanField(
        default=False,
        verbose_name='Выводить строчку домовых счетчиков'
    )
    show_house_utility_consumptions = BooleanField(
        default=False,
        verbose_name='Выводить домовые расходы по коммунальным услугам'
    )
    show_utility_consumptions_norms = BooleanField(
        required=True,
        default=True,
        verbose_name='Выводить расход тепла за минусом ГВС'
    )
    show_heat_consumtion_wo_hw = BooleanField(
        required=True,
        default=True,
        verbose_name='Выводить расход тепла за минусом ГВС'
    )
    avg_consumption_month = IntField(
        required=True,
        min_value=0,
        default=6,
        verbose_name=(
            'кол-во месяцев, в течении кот. разрешено '
            'начислять сред. индивид. показания'
        )
    )
    max_normative_month = IntField(
        required=True,
        min_value=0,
        default=1,
        verbose_name=(
            'начиная с какого месяца начислять по-нормативу или по-среднему'
        )
    )
    property_share_by_default = BooleanField(
        default=False,
        verbose_name='Начислять по площади от доли по умолчанию всегда'
    )
    closed_after_period = IntField()
    electricity_meters_infinite_consider = BooleanField(
        default=True,
        verbose_name='Учитывать счётчики электроэнергии бесконечно для '
                     'расчёта по среднему после закрытия',
    )
    privilege_return = BooleanField(null=True)
    meters_preservation = IntField(
        min_value=0,
        default=0,
        verbose_name=(
            'через сколько месяцев неподачи показаний консервировать счётчик'
        )
    )
    public_communal_services_recalc_type = StringField(
        choices=PUBLIC_COMMUNAL_SERVICES_RECALC_TYPE_CHOICES,
        default=PublicCommunalServicesRecalcType.NONE,
        verbose_name='Способ учёта перерасчёта отрицательных услуг ОДН',
    )
    public_communal_services_recalc_start_month = DateTimeField(
        default=datetime.datetime(2023, 1, 1),
        verbose_name='Месяц начала учёта перерасчёта отрицательных услуг ОДН',
    )

    def save(self, *args, **kwargs):
        if getattr(self, '_created') and not self.sectors:
            self.create_sector_settings()
        self.validate_sectors_settings()
        return super().save(*args, **kwargs)

    def validate_sectors_settings(self):
        """
        Удалит из настроек начислений направление, если оно:
        1. Удалено из привязки
        2. Не имеет начислений/оплат
        """
        provider, house = self._get_models(self.provider, self.house)

        bound_sectors = []
        for s_b in house.service_binds:
            if s_b.provider == self.provider:
                bound_sectors = [sector.sector_code for sector in s_b.sectors]

        accrual_setting_sectors = []
        for sector in self.sectors:
            if sector.sector_code not in bound_sectors:
                if not self._sector_has_turnovers(sector.sector_code):
                    continue
            accrual_setting_sectors.append(sector)
        self.sectors = accrual_setting_sectors

    def _sector_has_turnovers(self, sector_code):
        """
        True, если есть начисление или оплата в провайдере
         с направлением по дому
        Иначе False
        @param sector_code: str: Код направления
        """
        from processing.models.billing.accrual import Accrual
        from processing.models.billing.payment import Payment

        accruals = Accrual.objects(
            doc__provider=self.provider,
            account__area__house__id=self.house,
            sector_code=sector_code,
            is_deleted__ne=True,
        ).only(
            'id',
        ).first()

        payments = Payment.objects(
            doc__provider=self.provider,
            account__area__house__id=self.house,
            sector_code=sector_code,
            is_deleted__ne=True,
        ).only(
            'id',
        ).first()

        return any([accruals, payments])

    def create_sector_settings(self):
        """ Установка настроек по умолчанию """

        provider, house = self._get_models(self.provider, self.house)
        bank_account = (
            provider.bank_accounts[0].number
            if len(provider.bank_accounts) == 1
            else None
        )
        sectors = []
        for s_b in house.service_binds:
            if s_b.provider == self.provider:
                sectors = [i.sector_code for i in s_b.sectors]

        template_id = ReceiptTemplate.objects(use_default=True).first()
        template_id = (
            template_id.id
            if template_id
            else ObjectId("5968daa6b1352f004c2e38ed")
        )
        query = dict(provider=self.provider)
        tariff_plan = TariffPlan.objects(**query).order_by('-date_from').first()
        for sector in sectors:
            setting = self._create_default_sector_settings(
                sector=sector,
                sectors=sectors,
                template_id=template_id,
                bank_account=bank_account
            )
            setting.tariff_plan = (
                tariff_plan.id if tariff_plan else None
            )
            self.sectors.append(setting)

    @classmethod
    def _create_default_sector_settings(cls, sector, sectors,
                                        template_id, bank_account):

        if sector == 'capital_repair':
            p_settings = PenniesEmbedded(
                conditions=[
                    # Запись 1
                    ConditionsEmbedded(date=datetime.datetime(2000, 1, 1)),
                    # Запись 2
                    ConditionsEmbedded(
                        date=datetime.datetime(2016, 7, 1),
                        expiration_rates=[
                            ExpirationRatesEmbedded(
                                days_from=31
                            )
                        ]
                    ),
                ]
            )
        else:
            p_settings = PenniesEmbedded(
                conditions=[
                    # Запись 1
                    ConditionsEmbedded(date=datetime.datetime(2000, 1, 1)),
                    # Запись 2
                    ConditionsEmbedded(
                        date=datetime.datetime(2016, 7, 1),
                        expiration_rates=[
                            # 1
                            ExpirationRatesEmbedded(
                                days_from=31,
                                days_till=90
                            ),
                            # 2
                            ExpirationRatesEmbedded(
                                days_from=91
                            )
                        ]
                    ),
                ]
            )
        sector_settings = SectorSettings(
            bank_account=(
                bank_account
                if sector == 'rent' or ('rent' not in sectors)
                else None
            ),
            sector_code=sector,
            registry_meters=sector == 'rent',
            pennies=p_settings,
            area_types=[
                AreaTypeAccrualSettings(
                    template=[
                        TemplateSettings(
                            template=template_id,
                            date_from=datetime.datetime(2000, 1, 1),
                        )
                    ]
                )
            ]
        )
        return sector_settings

    def get_templates(self, sector, month_from=None):
        templates = {}
        sector_settings = self.get_sector_by_code(sector)

        for settings in sector_settings.area_types:
            if (sector, settings.type) in templates:
                raise ValidationError(
                    f'Шаблон типа {settings.type} дублируется в настройках, '
                    f'соответствующих документу начислений: {self.id}'
                )
            if len(settings.template) > 0:
                temp_list = sorted(
                    [
                        t for t in settings.template
                        if (
                            t.date_from
                            and t.date_from
                            <= (month_from or datetime.datetime.now())
                    )
                    ],
                    key=lambda i: i.date_from
                )
                if len(temp_list) > 0:
                    temp_settings = temp_list[-1]
                    templates[sector, settings.type] = temp_settings

        return templates

    @classmethod
    def _get_models(cls, provider_id, house_id):

        from app.house.models.house import House
        from processing.models.billing.provider.main import Provider

        fields = 'id', 'service_binds'
        house = House.objects(id=house_id).only(*fields).first()
        fields = 'id', 'bank_accounts'
        provider = Provider.objects(id=provider_id).only(*fields).first()

        return provider, house

    def get_sector_by_code(self, sector_code):
        sector_settings = [
            x
            for x in self.sectors
            if x.sector_code == sector_code
        ]
        return sector_settings[0]


class Settings(ProviderAccrualSettingsMixin, Document):
    """Общий класс для работы с настройками, имеющий все поля"""
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Settings'
    }

    # Услуга
    # Ref('ServiceType'),
    # 'processing.models.billing.service_type.ServiceType'
    service_type = ObjectIdField()

    # основные значения
    # Required(GeneralValues, default=GeneralValues)
    general = EmbeddedDocumentField(GeneralValues)

    # значения по домам
    # [HouseValues]
    by_houses = ListField(EmbeddedDocumentField(HouseValues))

    # Required(MainType)
    main_type = StringField(choices=MAIN_TYPE)

    # тип настройки
    # Required(String, default=Type.manual_operation)
    type = StringField(default=GeneralValueType.MANUAL_OPERATION)

    # справочник дебета
    # Required([String], default=[''])
    subconto_dt = ListField(StringField())

    # справочник кредита
    # Required([String], default=[''])
    subconto_ct = ListField(StringField())

    # счет дебета
    # Required(String, default='')
    debt_number = StringField()

    # счет кредита
    # Required(String, default='')
    credit_number = StringField()

    # настройки пеней
    # Required(Pennies, default=Pennies())
    pennies = EmbeddedDocumentField(PenniesEmbedded)

    # требуется ли загрузка льготников
    # Boolean
    required_load = BooleanField()

    # название шаблона
    # String
    template_name = StringField()

    # настройка для обработки файла льготников
    # [PrivilegeFile]
    file_settings = EmbeddedDocumentField(PrivilegeFileEmbedded)

    # PrivilegeFile
    default_file_setting = EmbeddedDocumentField(PrivilegeFileEmbedded)

    # Required(Boolean, default=True)
    is_system = BooleanField(default=True)
    penalties_month_offset = IntField()

    @classmethod
    def create_sector_settings(cls, house_id, provider_id, update=False):
        """ Установка настроек по умолчанию """

        provider, house = cls._get_models(provider_id, house_id)
        query = {
            'house': house_id,
            'provider': provider_id
        }
        exists_settings = cls.objects(__raw__=query).first()
        if exists_settings:
            if update:
                settings = exists_settings
            else:
                return
        else:
            settings = cls(
                house=house.id,
                provider=provider_id,
                sectors=[],
                area_meters_month_get=1,
                house_meters_month_get=1,
            )
        bank_account = (
            provider.bank_accounts[0].number
            if len(provider.bank_accounts) == 1
            else None
        )
        sectors = []
        for s_b in house.service_binds:
            if s_b.provider == provider_id:
                sectors = [i.sector_code for i in s_b.sectors]

        template_id = ReceiptTemplate.objects(use_default=True).first()
        template_id = (
            template_id.id
            if template_id
            else ObjectId("5968daa6b1352f004c2e38ed")
        )
        tariff_plan = TariffPlan.objects(
            provider=provider_id
        ).order_by('-date_from').first()
        for sector in sectors:
            sector_settings = None
            for s_s in settings.sectors:
                if s_s['sector_code'] == sector:
                    sector_settings = exists_settings
                    break
            if not sector_settings:
                setting = cls._create_default_sector_settings(
                    sector=sector,
                    sectors=sectors,
                    template_id=template_id,
                    bank_account=bank_account
                )
                setting.tariff_plan = (
                    tariff_plan.id if tariff_plan else None
                )
                settings.sectors.append(setting)
        settings.save()


class ProviderAccrualSettings(ProviderAccrualSettingsMixin, Document):
    """Класс для работы с настройками оплат организации"""
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Settings'
    }

    @classmethod
    def get_or_create_sector_settings(cls, house_id, provider_id):
        exists_settings = cls.objects(
            house=house_id,
            provider=provider_id,
        ).first()
        if exists_settings:
            return exists_settings
        settings = cls(
            house=house_id,
            provider=provider_id,
        )
        settings.save()
        return settings
