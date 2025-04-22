import copy
from datetime import datetime

import math
from bson import ObjectId
from dateutil.relativedelta import relativedelta
from math import trunc
from mongoengine import Document, EmbeddedDocument, \
    FloatField, StringField, IntField, DynamicField, EmbeddedDocumentField, \
    ObjectIdField, DateTimeField, ListField, EmbeddedDocumentListField, \
    DictField, Q
from mongoengine.fields import BooleanField

from app.gis.models.gis_queued import GisQueued
from app.gis.models.guid import GUID
from lib.dates import months_between
from lib.helpfull_tools import DateHelpFulls as dhf
from processing.data_producers.associated.base import \
    get_resource_accruals_by_area
from app.area.models.area import Area
from processing.models.billing.base import HouseGroupBinds, BindedModelMixin, \
    FilesDeletionMixin
from processing.models.billing.embeddeds.base import DenormalizedEmbeddedMixin
from processing.models.billing.common_methods import get_area_house_groups, \
    get_house_groups
from processing.models.billing.files import Files
from processing.models.billing.meter_event import MeterReadingEvent, \
    MeterReadingsChangedData
from processing.models.billing.meter_handbook import FLOWMETER_TYPE, \
    METER_MODEL, SPHERE_APPLICATION, V_CONVERSIONS, T_CONVERSIONS
from processing.models.billing.settings import ProviderAccrualSettings
from processing.models.choices import READINGS_CREATORS_CHOICES, \
    ReadingsCreator, GPRS_OPERATORS_CHOICES, GPRS_ADAPTER_MODELS_CHOICES
from app.meters.models.choices import METER_TYPE_NAMES, \
    MeterResourceType, MeterType, MeterMeasurementUnits as MeterUnit
from processing.models.exceptions import CustomValidationError


class Reading(EmbeddedDocument):
    id = ObjectIdField(db_field="_id", default=ObjectId)

    created_at = DateTimeField(
        required=True,
        default=datetime.now,
        verbose_name='Время создания',
    )
    period = DateTimeField(required=True, verbose_name='Месяц показаний')
    author = ObjectIdField(verbose_name='Автор')
    values = ListField(FloatField(), verbose_name='Показание')
    points = ListField(IntField(null=True), verbose_name='Баллы')
    deltas = ListField(FloatField(), verbose_name='Расход')
    created_by = StringField(
        choices=READINGS_CREATORS_CHOICES,
        verbose_name='Код источника показаний'
    )
    status = StringField(verbose_name='Статус')
    comment = StringField(verbose_name='Комментарий')
    recalculation = IntField(
        null=True,
        verbose_name='Информация о возможном перерасчёте'
    )

    @staticmethod
    def round_values(values: list) -> list:
        """Округление расхода / показаний"""
        return [float(f'{value:.6f}') for value in values] if values else []


class MeterEmbeddedHouse(DenormalizedEmbeddedMixin, EmbeddedDocument):
    id = ObjectIdField(db_field="_id")

    address = StringField()
    developer = DynamicField()

    @classmethod
    def from_house(cls, house):
        return cls(
            id=house.id,
            address=house.address,
        )


class MeterEmbeddedArea(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = "Area"

    id = ObjectIdField(db_field="_id", read_only=False)
    _type = ListField(StringField())

    house = EmbeddedDocumentField(MeterEmbeddedHouse)
    number = IntField()
    str_number = StringField()
    order = IntField()

    gis_uid = StringField()

    @classmethod
    def from_area(cls, area):
        return cls(
            id=area.id,
            _type=area._type,
            house=MeterEmbeddedHouse(
                id=area.house.id,
                address=area.house.address,
            ),
            number=area.number,
            str_number=area.str_number,
            order=area.order,
            gis_uid=area.gis_uid,
        )


class MeterCheckEmbedded(EmbeddedDocument):
    check_date = DateTimeField(
        verbose_name='Дата поверки счетчика'
    )
    expiration_date_check = IntField(
        verbose_name='Срок поверки, лет'
    )
    next_check_date = DateTimeField(
        verbose_name='Дата следующей поверки (окончания текущей)'
    )
    working_start_date = DateTimeField(
        verbose_name='Дата опломбировки счетчика'
    )
    attached_seal_act = EmbeddedDocumentField(
        Files,
        verbose_name='Акт пломбировки счетчика/основание установки заглушки'
    )
    attached_check_act = EmbeddedDocumentField(
        Files,
        verbose_name='Акт поверки счетчика'
    )
    seal_number = StringField(
        default='',
        null=True,
        verbose_name='Номер пломбы',
    )


class ReadingsValidationError(CustomValidationError):
    pass


class MeterDataValidationError(CustomValidationError):
    pass


class ReadingsExistValidationError(ReadingsValidationError):
    pass


CREATOR_PRIORITY = {
    'system': 120,
    'automatic': 120,
    'worker': 120,
    'tenant': 110,
    'registry': 100,
    'gis_system': 40,
    'gis_tenant': 20,
}
LIMITED_PERMISSIONS_CREATORS = (
    ReadingsCreator.TENANT, ReadingsCreator.REGISTRY,
    ReadingsCreator.GIS_TENANT, ReadingsCreator.GIS_SYSTEM
)
METER_TYPE_NORMA = {
    'ColdWaterAreaMeter': (6,),
    'HotWaterAreaMeter': (4,),
    'ElectricOneRateAreaMeter': (200,),
    'ElectricTwoRateAreaMeter': (200, 100),
    'ElectricThreeRateAreaMeter': (200, 200, 100),
    'HeatAreaMeter': (10000,),  # todo: Вернуть настоящее значение
    'HeatDistributorAreaMeter': (10000,),  # todo ????
    'GasAreaMeter': (30,),
}
METER_TYPE_LIMIT = {
    'ColdWaterAreaMeter': (3.5, 5),
    'HotWaterAreaMeter': (3.5, 5),
    'ElectricOneRateAreaMeter': (3.5, 5),
    'ElectricTwoRateAreaMeter': (3.5, 5),
    'ElectricThreeRateAreaMeter': (3.5, 5),
    'HeatAreaMeter': (3.5, 5),
    'HeatDistributorAreaMeter': (3.5, 5),
    'GasAreaMeter': (10, 15)


}
METER_RESOURCE = {
    'ColdWaterAreaMeter': ('cold_water',),
    'HotWaterAreaMeter': ('hot_water',),
    'ElectricOneRateAreaMeter': ('electricity_regular',),
    'ElectricTwoRateAreaMeter': ('electricity_day', 'electricity_night'),
    'ElectricThreeRateAreaMeter': (
        'electricity_peak', 'electricity_night', 'electricity_semi_peak'
    ),
    'HeatAreaMeter': ('heat',),
    'HeatDistributorAreaMeter': ('heat_distributor',),
    'GasAreaMeter': ('gas',),
    'WasteWaterAreaMeter': ('waste_water',),
    'ColdWaterHouseMeter': ('cold_water',),
    'HotWaterHouseMeter': ('hot_water',),
    'ElectricOneRateHouseMeter': ('electricity_regular',),
    'ElectricTwoRateHouseMeter': ('electricity_day', 'electricity_night'),
    'ElectricThreeRateHouseMeter': (
        'electricity_peak', 'electricity_night', 'electricity_semi_peak'
    ),
    'HeatHouseMeter': ('heat',),
    'GasHouseMeter': ('gas',),
    'WasteWaterHouseMeter': ('waste_water',)
}

RESOURCES_WITH_ROUND_CONSUMPTION_LIST = (
    'electricity_regular',
    'electricity_day',
    'electricity_night',
    'electricity_peak',
    'electricity_semi_peak'
)

METER_ORDER_BY_TYPE = {
    'ColdWaterAreaMeter': 30,
    'HotWaterAreaMeter': 60,
    'ElectricOneRateAreaMeter': 90,
    'ElectricTwoRateAreaMeter': 120,
    'ElectricThreeRateAreaMeter': 135,
    'HeatAreaMeter': 150,
    'HeatDistributorAreaMeter': 155,
    'GasAreaMeter': 180,
    'ColdWaterHouseMeter': 30,
    'HotWaterHouseMeter': 60,
    'ElectricOneRateHouseMeter': 90,
    'ElectricTwoRateHouseMeter': 120,
    'ElectricThreeRateHouseMeter': 135,
    'HeatHouseMeter': 150,
    'GasHouseMeter': 180,
}
METER_CHECK_INTERVAL_BY_TYPE = {
    'ColdWaterAreaMeter': 6,
    'HotWaterAreaMeter': 4,
    'ElectricOneRateAreaMeter': 12,
    'ElectricTwoRateAreaMeter': 12,
    'ElectricThreeRateAreaMeter': 12,
    'HeatAreaMeter': 6,
    'HeatDistributorAreaMeter': 6,
    'GasRateAreaMeter': 25,
}

ELECTRIC_METER = [
    MeterType.ELECTRIC_ONE_RATE_HOUSE_METER,
    MeterType.ELECTRIC_TWO_RATE_HOUSE_METER,
    MeterType.ELECTRIC_THREE_RATE_HOUSE_METER,
    MeterType.ELECTRIC_ONE_RATE_AREA_METER,
    MeterType.ELECTRIC_TWO_RATE_AREA_METER,
    MeterType.ELECTRIC_THREE_RATE_AREA_METER,
]
VOLUME_METER = [
    MeterType.HEAT_AREA_METER,
    MeterType.HEAT_HOUSE_METER,
    MeterType.HEAT_DISTRIBUTOR_AREA_METER,
    MeterType.HOT_WATER_HOUSE_METER,
]  # предоставляет объем потребленного коммунального ресурса

DEFAULT_OKEI_UNITS = {
    MeterType.COLD_WATER_AREA_METER: MeterUnit.CUBIC_METER,
    MeterType.COLD_WATER_HOUSE_METER: MeterUnit.CUBIC_METER,
    MeterType.HOT_WATER_AREA_METER: MeterUnit.CUBIC_METER,
    MeterType.HOT_WATER_HOUSE_METER: MeterUnit.CUBIC_METER,
    MeterType.ELECTRIC_ONE_RATE_AREA_METER: MeterUnit.KILOWATT_PER_HOUR,
    MeterType.ELECTRIC_ONE_RATE_HOUSE_METER: MeterUnit.KILOWATT_PER_HOUR,
    MeterType.ELECTRIC_TWO_RATE_AREA_METER: MeterUnit.KILOWATT_PER_HOUR,
    MeterType.ELECTRIC_TWO_RATE_HOUSE_METER: MeterUnit.KILOWATT_PER_HOUR,
    MeterType.ELECTRIC_THREE_RATE_AREA_METER: MeterUnit.KILOWATT_PER_HOUR,
    MeterType.ELECTRIC_THREE_RATE_HOUSE_METER: MeterUnit.KILOWATT_PER_HOUR,
    MeterType.GAS_AREA_METER: MeterUnit.CUBIC_METER,
    MeterType.GAS_HOUSE_METER: MeterUnit.THOUSAND_CUBIC_METERS,
    MeterType.HEAT_AREA_METER: MeterUnit.GIGACALORIE,
    MeterType.HEAT_DISTRIBUTOR_AREA_METER: '876',
    MeterType.HEAT_HOUSE_METER: MeterUnit.GIGACALORIE,
}

UNLIMITED_DELTA_METER_TYPES = [
    'HeatAreaMeter',
    'HeatDistributorAreaMeter',
]


class Meter(Document, BindedModelMixin):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Meter',

    }

    id = ObjectIdField(db_field="_id", primary_key=True)
    _type = ListField(StringField())
    is_deleted = BooleanField()

    ####
    # Meter
    ####
    communication = ObjectIdField(verbose_name='Привязка к вводу коммуникаций')
    readings = ListField(EmbeddedDocumentField(Reading))  # список снимаемых данных прибора учета
    attached_passport = DictField(null=True)  # File,  # Паспорт счетчика
    attached_seal_act = DictField(null=True)  # File,  # Акт пломбировки счетчика/основание установки заглушки
    description = StringField(null=True)  # Описание
    description_control = StringField()  # Описание до обновления 3.1
    expiration_date_check = IntField()  # PositiveInt,  # Срок годности поверки

    serial_number = StringField()  # All(String, lambda x: x.replace(':'', '')),  # Заводской номер
    serial_number_control = StringField()  # Заводской номер до обновления 3.1

    working_start_date = DateTimeField()  # DateTime,  # Дата начала учёта
    working_finish_date = DateTimeField(null=True)  # HistoryField(DateTime),  # Дата окончания учёта
    closed_by = StringField()  # Кем закрыт (тип, например, системой или сотрудником)

    first_check_date = DateTimeField()  # Required(DateTime),  # Дата первичной поверки
    last_check_date = DateTimeField()  # DateTime,  # Дата последней поверки
    next_check_date = DynamicField()  # Denormalized(),  # Дата следующей поверки
    #  История поверки счетчика
    check_history = EmbeddedDocumentListField(MeterCheckEmbedded)

    installation_date = DateTimeField()  # DateTime,  # Дата установки
    initial_values = ListField(FloatField())  # HistoryField([PositiveFloat]),  # список начальных значений счетчика
    average_deltas = ListField(FloatField())  # Optional([Float], soft_default=None),  # среднее значение расхода, расчитывается каждый раз при сдаче показаний

    ratio = IntField(required=True, default=1)  # Required(NaturalInt, default=1),  # Кооф. трансформации
    order = DynamicField()  # Denormalized(), #  Порядок сортировки
    created_by = DynamicField()

    # Код единицы измерений показаний счетчика по ОКЕИ
    unit_of_measurement_okei = StringField()

    ####
    # HouseMeter
    ####

    house = EmbeddedDocumentField(MeterEmbeddedHouse)
    adapter = DynamicField()
    mounting = StringField()
    loss_ratio = FloatField()
    digit_capacity = FloatField()
    install_at = DateTimeField()  # Date,  # дата установки прибора учета
    started_at = DateTimeField()  # Date,  # дата ввода в эксплуатацию прибора учета
    checked_at = DateTimeField()  # Date,  # дата проведения поверки прибора учета
    reference = BooleanField(null=True, verbose_name="Справочный счетчик")

    ####
    # AreaMeter
    ####

    area = EmbeddedDocumentField(MeterEmbeddedArea)
    # mounting = StringField()  # TenantInfo.Mounting,  # Расположение счётчика
    # digit_capacity = FloatField()  # Required(NaturalFloat, default=99999),  # Разрядность счётчика
    is_automatic = BooleanField()  # Required(Boolean, default=False),  # Автоматизированный счетчик
    # order = IntField()  # PositiveInt,
    reverse = BooleanField()  # Required(Boolean, default=False),  # Счётчик является обратным (Обратный счётчик)

    ####
    # HouseHeatMeter
    ####

    meter_model = DynamicField()  # MeterModel,  # В связи с автоматизацией добавляем
    flowmeter_type =DynamicField()  # FLOWMETER_TYPE,  # Тип расходомера
    sphere_application = DynamicField()  # SPHERE_APPLICATION,  # Сфера применения
    connection_schema = DynamicField()  # Required(ConnectionSchema, default=None),  # Схема соединения
    temperature_chart = StringField(r'^\d{2,3}/\d{2,3}$')  # Required(Match(r'^\d{2,3}/\d{2,3}$'), default=None),  # т. график
    pressure_transformer = DynamicField()  # Required(Any(V_CONVERSIONS, NString), default=None),  #
    winter_calc_formula = DynamicField()  # HistoryField(NString),  # формула подсчета теплоты.
    summer_calc_formula = DynamicField()  # HistoryField(NString),  # =/=
    code_uute =StringField()  # String,  # узел учета тепловой энергии
    heat_systems = DynamicField()  # [HeatSystem],  # Тепловая система
    season_change = DynamicField()  # [SeasonChange],  # Смена времени года
    equip_info = DynamicField()  # [EquipInfo],  # Дополнительная информация по счетчику

    address = StringField()  # String,  # обслуживаемый адрес
    expances = DynamicField()  # House.HeatingContract.Expances,  # договорные нагрузки

    tolerance_dt = IntField()  # Required(PositiveInt, default=3),  # допустимое отклонение dT
    allowable_unbalance_mass = IntField()  # Required(PositiveInt, default=2),  # допустимый небаланс масс

    ####
    # ?
    ####

    sim_number = DynamicField()
    app_number = DynamicField()
    phone_number = DynamicField()
    account_number = DynamicField()

    ####
    # GIS
    ####

    gis_uid = StringField()
    model_name = StringField()  # название модели прибора
    brand_name = StringField()  # название марки прибора
    temperature_sensor = BooleanField()  # Наличие датчика температуры
    pressure_sensor = BooleanField()  # Наличие датчика давления
    change_meter_date = DateTimeField(
        null=True,
        verbose_name='Дата окончания учёта',
    )

    _binds = EmbeddedDocumentField(
        HouseGroupBinds,
        verbose_name='Привязки к группе домов'
    )

    def save(self, *arg, **kwargs):
        raise TypeError('Use AreaMeter or HouseMeter')

    @classmethod
    def process_house_binds(cls, house_id):
        pass


class BasicMeter(FilesDeletionMixin):
    """ Общие поля для всех видов счетчиков """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Meter',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            '_binds.hg',
            'working_finish_date',
            # {
            #     'name': 'calculate_accruals',
            #     'fields': [
            #         'area.house.id',
            #         'working_start_date',
            #     ],
            # },
        ],
    }
    _type = ListField(StringField())
    is_deleted = BooleanField()

    readings = EmbeddedDocumentListField(
        Reading,
        verbose_name='список снимаемых данных прибора учета'
    )
    attached_passport = EmbeddedDocumentField(
        Files,
        verbose_name='Паспорт счетчика',
    )
    loss_ratio = FloatField(verbose_name='Коэфф потерь')
    description = StringField(null=True, verbose_name='Описание')
    expiration_date_check = IntField(verbose_name='Срок годности поверки')

    serial_number = StringField(verbose_name='Заводской номер')

    ####
    # Поверка
    ####
    check_history = EmbeddedDocumentListField(
        MeterCheckEmbedded,
        verbose_name='История поверки счетчика'
    )
    # todo: Не забыть перемигрировать в нулевую запись новой истории поверки
    attached_seal_act = EmbeddedDocumentField(
        Files,
        verbose_name='Акт пломбировки счетчика/основание установки заглушки'
    )
    # todo: Не забыть перемигрировать в нулевую запись новой истории поверки
    working_start_date = DateTimeField(
        null=True,  # TODO: Сделать обязательным, но падает импорт из ГИС
        verbose_name='Дата начала учёта',
    )
    # todo: Не забыть перемигрировать в Вальхаллу (если показать поле,
    #  будут вопросы, ранее его не было видно)
    first_check_date = DateTimeField(
        null=True,
        verbose_name='Дата первичной поверки',
    )
    # todo: Не забыть перемигрировать в нулевую запись новой истории поверки
    last_check_date = DateTimeField(
        null=True,
        verbose_name='Дата последней поверки',
    )
    # todo: Не забыть перемигрировать в нулевую запись новой истории поверки
    next_check_date = DateTimeField(
        null=True,
        verbose_name='Дата следующей поверки',
    )

    ####

    working_finish_date = DateTimeField(
        null=True,
        verbose_name='Дата окончания учёта',
    )
    change_meter_date = DateTimeField(
        null=True,
        verbose_name='Дата окончания учёта',
    )
    closed_by = StringField(
        null=True,
        verbose_name='Кем закрыт (тип, например, системой или сотрудником)'
    )

    installation_date = DateTimeField(verbose_name='Дата установки')
    initial_values = ListField(
        FloatField(),
        verbose_name='Список начальных значений счетчика'
    )
    average_deltas = ListField(
        FloatField(),
        verbose_name='Среднее значение расхода, расчитывается каждый '
                     'раз при сдаче показаний'
    )

    ratio = IntField(required=True,
                     default=1,
                     verbose_name='Кооф. трансформации')
    order = IntField(verbose_name='Порядок сортировки')
    created_by = ObjectIdField()
    model_name = StringField(
        null=True,
        verbose_name='Название модели прибора',
    )
    brand_name = StringField(
        null=True,
        verbose_name='Название марки прибора',
    )
    gis_uid = StringField(
        null=True,
        verbose_name='ИД в ГИС',
    )

    unit_of_measurement_okei = StringField(
        null=True,
        verbose_name='Код единицы измерений показаний счетчика по ОКЕИ'
    )

    @staticmethod
    def working_meter_query(moment: datetime = None) -> dict:
        """Фрагмент запроса действующих ПУ"""
        if not moment:
            moment = datetime.now()

        return {
            'working_start_date': {'$not': {'$gt': moment}},  # null or lte
            'working_finish_date': {'$not': {'$lte': moment}},  # null or gt
            'is_deleted': {'$ne': True},  # null or false
        }

    @staticmethod
    def closed_meter_query(moment: datetime = None) -> dict:
        """Фрагмент запроса недействующих/закрытых ПУ"""
        if not moment:
            moment = datetime.now()

        return {
            'working_finish_date': {'$lte': moment},
            # меньше или равно текущей дате (уже закрыты)
            'is_deleted': {'$ne': True},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.safely_readings_added = False
        self.readings_change_log = []

    @property
    def period_readings(self) -> dict:
        """Показания по периодам"""
        return {reading.period: reading.values for reading in self.readings}

    @property
    def last_reading_period(self) -> datetime:
        """Последний период внесенных показаний"""
        assert self.readings, "Внесенные показания отсутствуют"
        return sorted(self.period_readings)[-1]  # первый ключ с конца

    @property
    def rate_count(self) -> int:
        """Количество тарифов"""
        return 3 if self.resource_type in MeterResourceType.THREE_RATE \
            else 2 if self.resource_type in MeterResourceType.TWO_RATE \
            else 1  # self.resource_type in MeterResourceType.ONE_RATE

    @property
    def is_area_meter(self):
        return next((True for x in self._type if 'Area' in x), False)

    @property
    def is_house_meter(self):
        return next((True for x in self._type if 'House' in x), False)

    @property
    def meter_type(self) -> str:
        """Тип прибора учета - ИПУ (AreaMeter) или ОДПУ (HouseMeter)"""
        return self.__class__.__name__

    @property
    def resource_type(self) -> str:
        """Тип (потребляемого) ресурса прибора учета"""
        return self._type[0]  # всегда первый элемент

    @property
    def default_initial_values(self) -> list:
        """Начальные показания по умолчанию"""
        initial_date = self.first_check_date or \
            self.installation_date or self.working_start_date
        if initial_date is not None and self.readings:  # дата и показания?
            initial_period = initial_date.replace(day=1,
                hour=0, minute=0, second=0, microsecond=0)  # 1 число, полночь
            initial_reading = next(iter(reading for reading in self.readings
                if reading.period == initial_period), None)
            if initial_reading is not None:
                self.initial_values = initial_reading.values  # values ~ deltas
        else:  # нет показаний!
            return [0.0] * self.rate_count  # по количеству тарифов

    _EXPORT_CHANGES_FIELDS = [
        'serial_number',
        'brand_name', 'model_name',
        'unit_of_measurement_okei',
        'installation_date',
        'working_start_date',
        'working_finish_date',
        'house', 'area', 'mounting', '_type',
        'initial_values', 'communication',
        'check_history',
    ]  # TODO пополнить список подлежащих выгрузке полей

    @property
    def must_export_changes(self) -> bool:
        """
        Подлежит выгрузке в ГИС ЖКХ?

        ВНИМАНИЕ! Теряет актуальность после save
        """
        return bool(
            # возвращает список измененных полей или True при _created
            self._is_triggers(self._EXPORT_CHANGES_FIELDS)
        )

    def delete(self, signal_kwargs=None, **write_concern):
        self.is_deleted = True
        self.mark_communication_as_not_bonded()
        return getattr(super(), 'save')(signal_kwargs, **write_concern)

    def mark_communication_as_not_bonded(self):
        meter_cm = getattr(self, 'communication', None)
        if self.is_area_meter and meter_cm:
            area_id = getattr(self, 'area').id
            area = Area.objects(pk=area_id, communications__id=meter_cm).first()
            if not area:
                return

            for cm in area.communications:
                if cm.id == meter_cm:
                    dnt = datetime.now()
                    other_active_cm_meters = getattr(self.__class__, 'objects')(
                        __raw__={
                            'area._id': area_id,
                            'communication': meter_cm,
                            'is_deleted': {'$ne': True},
                            '_id': {'$ne': getattr(self, 'id')},
                            '$or': [
                                {'working_finish_date': {'gte': dnt}},
                                {'working_finish_date': None}
                            ]
                        }
                    ).count()
                    if not other_active_cm_meters:
                        cm.is_bonded = False
                    area.save()
                    return

    def check_loss_ratio(self,):
        if (
                True in list(map(lambda x: x in ELECTRIC_METER, self._type))
                and not self.loss_ratio
        ):
            self.loss_ratio = 1

    def check_meter_documents(self):
        if not self.attached_passport or not self.attached_passport.file:
            delattr(self, 'attached_passport')
        if not self.attached_seal_act or not self.attached_seal_act.file:
            delattr(self, 'attached_seal_act')

    def correct_empty_readings(self):
        if not self.readings:
            # mongoengine удаляет поля с пустыми списками
            readings_after_save = self.__class__.objects(
                pk=self.pk,
            ).only(
                'readings',
            ).as_pymongo().get()
            if readings_after_save.get('readings') is None:
                self.__class__.objects(
                    pk=self.pk,
                ).update(
                    __raw__={
                        '$set': {'readings': []},
                    },
                )

    def save(self, *args, **kwargs):
        assert isinstance(self, (AreaMeter, HouseMeter))

        if not self.readings:
            self.readings = []
        self.check_meter_documents()
        self.check_initial_values()
        self.check_type()
        self.check_loss_ratio()
        self.set_default_unit()
        self.handle_resurrected()

        must_export_changes: bool = self.must_export_changes  # до save
        result = getattr(super(), 'save')(*args, **kwargs)

        self.correct_empty_readings()

        if must_export_changes:
            GisQueued.put(self, hours=2)

        return result

    def handle_resurrected(self):
        # Счетчик восстановлен, убрана дата завершения?
        if self._is_key_dirty('working_finish_date') and not self.working_finish_date:
            gis_queue = GisQueued.objects(object_id=self.pk).first()
            # Есть в очереди?
            if gis_queue:
                gis_queue.delete()
            # Если нет в очереди, значит уже был закрыт ранее, открываем новый
            if not gis_queue:
                guid = GUID.objects(object_id=self.pk).first()
                if guid:
                    guid.delete()

    def set_default_unit(self):
        if not self.unit_of_measurement_okei:
            self.unit_of_measurement_okei = \
                DEFAULT_OKEI_UNITS.get(self._type[0])

    def check_type(self):
        """
        Проверяет и, если нужно, автоматически подставляет
        тип зависящий от класса
        """
        if self.meter_type not in self._type:
            self._type.append(self.meter_type)

    def check_initial_values(self):
        if self._is_key_dirty('initial_values') and self.readings:
            old_data = self.__class__.objects(
                pk=self.pk,
            ).as_pymongo().only(
                'initial_values',
            ).get()
            for ix, value in enumerate(self.initial_values):
                delta = value - old_data['initial_values'][ix]
                for readings in self.readings:
                    readings.values[ix] += delta
            # raise MeterDataValidationError(
            #     'Начальные показания уже заданы!'
            # )

    def add_closing_values(self, provider_id, account_id, values,
                           default_period=None, change_meter_date=None):
        """ Закрытие счетчика """
        period = self._get_period(provider_id, default_period)
        self.add_readings(
            period=period,
            values=values,
            actor_id=account_id,
            creator='worker',
            allow_float=True,
            change_meter_date=change_meter_date,
        )

    _FLOAT_READINGS_ALLOW_TYPES = (
        'HeatAreaMeter',
        'HeatDistributorAreaMeter',
        'HeatHouseMeter',
        'HotWaterHouseMeter',
        'ColdWaterHouseMeter',
        'GasHouseMeter',
        'ElectricOneRateHouseMeter',
        'ElectricTwoRateHouseMeter',
        'ElectricThreeRateHouseMeter',
    )
    _DELTAS_READINGS_ALLOW_TYPES = (
        'HeatAreaMeter',
        'HeatDistributorAreaMeter',
        'HeatHouseMeter',
        'HotWaterHouseMeter',
    )

    def is_preserved(self, interval: int) -> bool:
        """
        Законсервирован при непредоставлении показаний?
        """
        if interval == 0 or len(self.readings) == 0:
            return False  # нет ограничения или показаний

        last_reading = self.readings[-1]
        last_allowed = datetime.now() - relativedelta(months=interval)

        if last_allowed < last_reading.created_at:  # принято недавно
            return False  # имеются актуальные показания

        return True  # показания не могут быть приняты!

    def add_readings(self, period, values, creator, actor_id,
                     values_are_deltas=False, comment=None, allow_float=False,
                     change_meter_date=None, points=None):
        """
        Добавляет показания по счётчику. Не сохраняет. При невозможности
        добавить показания генерирует специальное исключение. Параметр
        values_are_deltas сообщает, что показания надо сохранить не как сами
        показания, а как расход (это будет сделано только для некоторых типов
        счётчиков, иначе будет исключение). Требования к показаниям и
        исключения:
        1. показания должны быть последними
        2. количество показаний должно соответствовать типу счётчика
        3. показания не должны выходить за рамки действия счётчика
        4. дробные показания разрешены только некоторым типам счётчиков
        5. отрицательные показания запрещены
        6. показания с отрицательным расходом могут подать не все источники
        7. показания, превышающие предел, могут подать не все источники
        8. Изменить существующие показания могут только некоторые источники
        """
        # валидируем исходные параметры
        if change_meter_date:
            self.change_meter_date = change_meter_date
        if self.working_finish_date:
            if self.working_finish_date < dhf.begin_of_month(period):
                raise ReadingsValidationError('Прибор учёта уже закрыт')
        if self.working_start_date.replace(day=1) > period.replace(day=2):
            raise ReadingsValidationError('Период раньше начала учёта')
        if len(self.initial_values) != len(values):
            raise ReadingsValidationError(
                'Количество показаний не соответствует прибору учёта'
            )
        if values_are_deltas and self.is_area_meter:
            deltas_meter = \
                self._type[0] in self._DELTAS_READINGS_ALLOW_TYPES
            if not (deltas_meter or all([v == 0 for v in values])):
                raise ReadingsValidationError(
                    'По данному типу прибора запрещено сдавать раход'
                )
        else:
            if any([v < 0 for v in values]):
                raise ReadingsValidationError(
                    'Отрицательные показания не разрешены'
                )
        for ix, v in enumerate(values):
            if not isinstance(v, int):
                if isinstance(v, float) and not math.isnan(v):
                    float_meter = \
                        self._type[0] in self._FLOAT_READINGS_ALLOW_TYPES
                    if not (allow_float or float_meter):
                        try:
                            values[ix] = int(v)
                        except ValueError:
                            raise ReadingsValidationError(
                                'Тип показаний не соответствует прибору учёта'
                            )
                else:
                    raise ReadingsValidationError(
                        'Тип показаний не соответствует прибору учёта'
                    )
        # ищем предыдущие и текущие показания
        last_values = self.initial_values
        current_readings = None
        if len(self.readings) > 0:
            if self.readings[-1].period > period:
                raise ReadingsValidationError(
                    'Разрешено менять только последние показания'
                )
            elif self.readings[-1].period == period:
                # меняем показания в текущем месяце
                current_readings = self.readings[-1]
                if len(self.readings) > 1:
                    last_values = self.readings[-2].values
            else:
                last_values = self.readings[-1].values
        # валидируем ещё раз количество показаний
        if len(last_values) != len(values):
            raise ReadingsValidationError(
                'Количество показаний не соответствует прибору учёта'
            )
        # провалидируем попытку заменить более важные показания
        if current_readings:
            current_creator = current_readings.created_by
            if CREATOR_PRIORITY[creator] < CREATOR_PRIORITY[current_creator]:
                raise ReadingsValidationError(
                    'Запрещено менять существующие показания'
                )
        # определяем расход
        if values_are_deltas:
            deltas = copy.copy(values)
            values = [last_values[ix] + v for ix, v in enumerate(values)]
        else:
            deltas = [v - last_values[ix] for ix, v in enumerate(values)]
            values = copy.copy(values)
        # проверим переход через ноль
        zero_limit = trunc(self.digit_capacity) + 1
        for ix, val in enumerate(values):
            if val >= zero_limit:
                values[ix] = val - zero_limit
            if abs(deltas[ix]) > zero_limit / 2:
                deltas[ix] = (
                        (abs(deltas[ix]) - zero_limit)
                        * round(deltas[ix] / abs(deltas[ix]))
                )
        # валидируем расход для жителей и реестров, выясним особый статус
        status = 'ok'
        for ix, delta in enumerate(deltas):
            if delta < 0:
                if creator in LIMITED_PERMISSIONS_CREATORS:
                    raise ReadingsValidationError(
                        'Показания должны быть больше предыдущих'
                    )
                status = 'negative'
            # TODO А что вслучае домового
            elif delta > 0 and self.is_area_meter:
                normas = METER_TYPE_NORMA.get(self._type[0])
                if normas and ix < len(normas):
                    no_check_norma = normas[ix] * 3.5
                else:
                    no_check_norma = 10000
                if delta <= no_check_norma:
                    continue
                average_delta = self.get_average_delta(ix, current_readings)
                if delta > average_delta * METER_TYPE_LIMIT[self._type[0]][0]:
                    if creator in LIMITED_PERMISSIONS_CREATORS and \
                            self._type[0] not in UNLIMITED_DELTA_METER_TYPES:
                        raise ReadingsValidationError(
                           f'Показания не должны превышать средний расход '
                           f'в {METER_TYPE_LIMIT.get(self._type[0])[0]} '
                           f'раз(-а)'
                        )
                    status = 'strange'
                if delta > average_delta * METER_TYPE_LIMIT[self._type[0]][1]:
                    status = 'maybe_error'
        # определим предполагаемый перерасчёт
        recalculation = self._get_recalculation_info(period)
        # добавляем показания
        if current_readings:
            current_readings.author = actor_id
            current_readings.created_by = creator
            current_readings.status = status
            current_readings.comment = comment
            current_readings.recalculation = recalculation
            current_readings.created_at = datetime.now()
            readings_event = MeterReadingEvent(
                _type=['MeterReadingChangedEvent', 'MeterReadingEvent'],
                meter=getattr(self, 'pk'),
                created_by=actor_id,
                source=creator,
                period=period,
            )
            if values_are_deltas:
                readings_event.deltas = MeterReadingsChangedData(
                    new=deltas,
                    old=current_readings.deltas,
                )
            else:
                readings_event.deltas = MeterReadingsChangedData(
                    new=values,
                    old=current_readings.values,
                )
            self.readings_change_log.append(readings_event)
            current_readings.values = values
            current_readings.points = points
            current_readings.deltas = deltas
        else:
            self.readings.append(Reading(
                id=ObjectId(),
                period=period,
                author=actor_id,
                values=self._round_values(values),
                points=points,
                deltas=self._round_values(deltas),
                created_by=creator,
                status=status,
                comment=comment,
                recalculation=recalculation
            ))
            readings_event = MeterReadingEvent(
                _type=['MeterReadingAddedEvent', 'MeterReadingEvent'],
                meter=getattr(self, 'pk'),
                created_by=actor_id,
                source=creator,
                period=period,
            )
            if values_are_deltas:
                readings_event.deltas = MeterReadingsChangedData(new=deltas)
            else:
                readings_event.deltas = MeterReadingsChangedData(new=values)
            self.readings_change_log.append(readings_event)
        self.safely_readings_added = True

    def delete_readings(self, period):
        """Поиск показания за переданный период и попытка его удаления"""
        if period == self.readings[-1].period:
            del self.readings[-1]
            self.safely_readings_added = True
            self.save(ignore_meter_validation=True)
        else:
            raise ReadingsValidationError(
                'Нельзя удалять показания, которые не являются последними!'
            )

    def get_average_delta(self, value_number=0, current_readings=None):
        """
        Возвращает средний расход по счётчику
        :current_readings: флаг изменения текущих показаний, для того
        чтобы не учитывать их при расчете среднего расхода
        """
        if len(self.readings) == 0:
            return 0
        if current_readings and len(self.readings) > 1:
            last_period = self.readings[-2].period
            readings = self.readings[:-1]
        else:
            last_period = self.readings[-1].period
            readings = self.readings
        first_period = self.working_start_date
        limit_date = last_period - relativedelta(years=1)
        sorted_readings = sorted(
            [
                (r.deltas[value_number], r.period)
                for r in readings
                if value_number < len(r.deltas)
            ],
            key=lambda x: x[1],
            reverse=True,
        )
        result = 0
        for data in sorted_readings:
            if data[1] > limit_date:
                result += data[0]
            else:
                first_period = data[1]
                break
        if not sorted_readings or result <= 0:
            return 0
        months = months_between(first_period, last_period) - 1
        return result / months if months > 0 else 0

    def _get_recalculation_info(self, period):
        """
        Получает информацию о возможном перерасчёте при подаче показаний за
        переданый месяц
        """
        # TODO А если нет квартиры
        if self.is_house_meter:
            return

        if len(self.readings) == 0:
            month_start = self.working_start_date - relativedelta(months=1)
        elif self.readings[-1].period == period:
            if len(self.readings) > 1:
                month_start = self.readings[-2].period
            else:
                month_start = self.working_start_date - relativedelta(months=1)
        else:
            month_start = self.readings[-1].period
        months = months_between(month_start, period) - 2
        if months <= 0:
            return None
        accruals = get_resource_accruals_by_area(
            getattr(getattr(self, 'area'), 'id'),
            METER_RESOURCE[self._type[0]],
            month_start - relativedelta(months=1),
            period,
        )
        if not accruals:
            return None
        provider = accruals[0]['owner']
        month_inc = self._get_area_meters_month_get_setting(provider)
        accruals_month_till = period - relativedelta(months=1 - month_inc)
        accruals_month_from = (
                accruals_month_till - relativedelta(months=months - 1)
        )
        result = 0
        for a in accruals:
            if accruals_month_from <= a['month'] <= accruals_month_till:
                result -= a['value']
        return result

    def _get_area_meters_month_get_setting(self, provider_id):
        """
        Получает настройку, в какой месяц идёт показание у организации
        """
        area_house_id = getattr(getattr(getattr(self, 'area'), 'house'), 'id')
        a_settings = ProviderAccrualSettings.objects(
            _type='ProviderAccrualSettings',
            provider=provider_id,
            house=area_house_id,
        ).as_pymongo().only('area_meters_month_get').first()
        return a_settings['area_meters_month_get'] if a_settings else None

    def _get_period(self, provider_id, default_period):

        from app.accruals.models.accrual_document import AccrualDoc

        # TODO
        house_id = (
            getattr(getattr(getattr(self, 'area'), 'house'), 'id')
            if self.is_area_meter
            else getattr(getattr(self, 'house'), 'id')
        )
        doc_query = dict(__raw__={'house._id': house_id})
        doc = AccrualDoc.objects(**doc_query).order_by('-date_from').first()

        settings_query = dict(
            __raw__={'house': house_id, 'provider': provider_id}
        )
        settings = ProviderAccrualSettings.objects(**settings_query).first()
        if not settings:
            raise MeterDataValidationError(
                "Для указаного дома не найдено настроек начислений"
            )
        period = dhf.begin_of_month(default_period or datetime.now())
        if settings.area_meters_month_get_usage:
            if doc:
                delta = 1 - int(settings.area_meters_month_get)
                period = max(
                    doc.date_from + relativedelta(months=delta),
                    period
                )
        return period

    def _next_check_date_denormalize(self, check_record):
        check_interval = [
            METER_CHECK_INTERVAL_BY_TYPE.get(x)
            for x in self._type
            if METER_CHECK_INTERVAL_BY_TYPE.get(x)
        ]
        check_interval = check_interval[0] if check_interval else None

        check_period = check_record.expiration_date_check or check_interval
        if check_record.check_date and check_period:
            check_record.next_check_date = (
                    check_record.check_date +
                    relativedelta(years=int(check_period))
            )
        return check_record

    def _check_history_denormalize(self):
        check_history = sorted(
            self.check_history,
            key=lambda record: record.check_date)
        check_history = list(map(self._next_check_date_denormalize,
                                 check_history))
        first_check_record = check_history[0]
        last_check_record = check_history[-1]

        self.first_check_date = first_check_record.check_date
        if first_check_record.working_start_date:
            self.working_start_date = first_check_record.working_start_date
        self.last_check_date = last_check_record.check_date
        self.next_check_date = last_check_record.next_check_date
        self.expiration_date_check = last_check_record.expiration_date_check

    def _order_denormalize(self):
        order = [
            METER_ORDER_BY_TYPE.get(x)
            for x in self._type
            if METER_ORDER_BY_TYPE.get(x)
        ]
        order = order[0] if order else 00
        self.order = order * 10

    def _validate_working_period(self):
        """
        Проверяет валидность периода работы счётчика. Начало и конец периода не
        должны конфликтовать с периодами показаний
        """
        if len(self.readings) == 0:
            return True
        if (
            dhf.begin_of_month(self.working_start_date) >
            dhf.begin_of_month(self.readings[0].period)
        ):
            raise MeterDataValidationError(
                f'Введенные показания могут быть сохранены только в месяц '
                f'потребления {self._parse_date(self.working_start_date)}, '
                f'т. к. предыдущие периоды закрыты для редактирования'
            )
        if (
            self.working_finish_date and
            dhf.begin_of_month(self.working_finish_date) <
            dhf.begin_of_month(self.readings[-1].period)
        ):
            raise MeterDataValidationError(
                f'Для сохранения показаний дата замены счетчика также '
                f'должна быть в периоде '
                f'{self._parse_date(self.readings[-1].period)} или в '
                f'позднем периоде'
            )
        return True

    def _parse_date(self, date: datetime):
        month = {
            1: 'Январь',
            2: 'Февраль',
            3: 'Март',
            4: 'Апрель',
            5: 'Май',
            6: 'Июнь',
            7: 'Июль',
            8: 'Август',
            9: 'Сентябрь',
            10: 'Октябрь',
            11: 'Ноябрь',
            12: 'Декабрь',
        }
        parse_date = f'{month[date.month]} {date.year}'
        return parse_date

    def close(self, date: datetime = None, by_system: bool = False):
        """Закрыть прибор учета"""
        self.working_finish_date = date or datetime.now()
        self.closed_by = 'system' if by_system else 'worker'

    def get_meter_type(self):
        return [
            x for x in self._type if x not in ('AreaMeter', 'HouseMeter')
        ][0]

    def _round_values(self, values):
        return [float(f"{x:.6f}") for x in values]

    @classmethod
    def update_gis_data(cls, meter_id: ObjectId, unified_number: str):
        """Обновить уникальный номер прибора учета"""
        assert issubclass(cls, (AreaMeter, HouseMeter))
        cls.objects(id=meter_id).update_one(
            set__gis_uid=unified_number,
            upsert=False  # не создавать новые документы
        )


class TenantInfoEmbedded(EmbeddedDocument):
    description = StringField(verbose_name='Описание')
    serial_number = StringField(verbose_name='Заводской номер')
    mounting = StringField(verbose_name='Расположение счётчика')
    attached_passport = EmbeddedDocumentField(
        Files,
        verbose_name='Паспорт счетчика'
    )
    attached_seal_act = EmbeddedDocumentField(
        Files,
        verbose_name='Акт пломбировки счетчика/основание установки заглушки'
    )


class AreaMeter(BasicMeter, Document, BindedModelMixin):
    """ Квартирный счетчик """

    area = EmbeddedDocumentField(MeterEmbeddedArea)
    mounting = StringField(verbose_name='Расположение счётчика')
    is_automatic = BooleanField(verbose_name='Автоматизированный счетчик')
    reverse = BooleanField(
        default=False,
        verbose_name='Счётчик является обратным (Обратный счётчик)'
    )
    communication = ObjectIdField(verbose_name='Привязка к вводу коммуникаций')
    digit_capacity = FloatField(
        required=True,
        default=99999.999,
        verbose_name='Разрядность счётчика',
    )
    _binds = EmbeddedDocumentField(
        HouseGroupBinds,
        verbose_name='Привязки к группе домов'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.old_communication = self.communication
        self.ignore_meter_validation = False

    @staticmethod
    def data_for_cabinet(meter, current_period):
        if (
                meter.get('working_finish_date') is not None
                and meter['working_start_date'] < datetime.now()
        ):
            working_finish_date = meter['working_finish_date']
        else:
            working_finish_date = None
        last_readings = meter['readings'][-1] if meter['readings'] else None
        previous_values = meter['initial_values']
        previous_date = None
        current_values = None
        for ix, r in enumerate(reversed(meter['readings'])):
            if r['period'] == current_period:
                current_values = r['values']
            if r['period'] < current_period:
                previous_values = r['values']
                previous_date = r['created_at']
                break
        average_deltas = meter.get('average_deltas')
        if not average_deltas:
            average_deltas = AreaMeter.get_average_deltas(
                meter['readings'],
                meter['initial_values'],
            )
        return {
            'id': meter['_id'],
            'type': meter['_type'][0],
            'serial_number': meter['serial_number'],
            'location': meter.get('mounting') or '',
            'installation_date': meter['installation_date'],
            'working_finish_date': working_finish_date,
            'working_start_date': meter['working_start_date'],
            'last_check_date': (meter.get('last_check_date')
                                or meter.get('first_check_date')),
            'next_check_date': meter['next_check_date'],
            'current_values': current_values,
            'previous_values': previous_values,
            'previous_date': previous_date,
            'last_readings_date': (
                    last_readings['created_at']
                    if last_readings else None
            ),
            'last_readings': last_readings['values'] if last_readings else None,
            'is_automatic': meter.get('is_automatic', False),
            'reverse': meter.get('reverse', False),
            'average_deltas': average_deltas,
            'readonly': AreaMeter.is_read_only_for_cabinet(meter),
            'digit_capacity': meter['digit_capacity'],
        }

    @property
    def data_for_tg_bot(self):
        """Отдаёт данные в формате пригодном для телеграм бота."""
        meter_type_code = (set(self._type) - {'AreaMeter'}).pop()
        meter_type_name = next(
            (name[1] for name in METER_TYPE_NAMES
             if name[0] == meter_type_code),
            ''
        )
        if not len(self.readings):
            last_values = self.initial_values
        else:
            last_values = self.readings[-1].values
        return {
            'id': str(self.id),
            # 'name': f'{meter_type_name} № {self.serial_number}'.lower(),
            'type': meter_type_name,
            'last_value': last_values,
            'serial_number': self.serial_number,
            'location': self.mounting
        }

    def save(self, *args,  **kwargs):
        if not self.ignore_meter_validation:
            self._check_history_denormalize()
        if not self.id:
            self._area_denormalize()
            self._order_denormalize()
        if (
                not kwargs.get('ignore_meter_validation')
                and not self.ignore_meter_validation
        ):
            self._validate_working_period()
            self._before_save()
        if self.safely_readings_added:
            self.update_average_deltas()
        if (
                not self.safely_readings_added
                and self.pk
                and not kwargs.get('ignore')
        ):
            if not self._check_readings_change():
                raise ReadingsValidationError(
                    'Небезопасное изменение показаний'
                )
        if not self._binds:
            self._binds = HouseGroupBinds(hg=self._get_house_binds())
        self.restrict_changes()
        self._denormalize_area_communication_bond()
        result = super().save(*args,  **kwargs)
        # сохранение событий об изменении показаний
        for readings_event in self.readings_change_log:
            readings_event.save()

        return result

    def update_average_deltas(self):
        count = len(self.readings)
        deltas = [i.deltas for i in self.readings]
        for ix in range(len(self.average_deltas)):
            if count == 0:
                self.average_deltas[ix] = 0
            else:
                self.average_deltas[ix] = sum(d[ix] for d in deltas) / count

    def _get_house_binds(self):
        return get_area_house_groups(self.area.id, self.area.house.id)

    def _get_area_model_by_communication(self):
        if not self.old_communication:
            return Area.objects(pk=self.area.id).get()
        area = Area.objects(
            pk=self.area.id,
            communications__id=self.old_communication
        ).first()
        if not area:
            raise MeterDataValidationError(
                'Такого ввода коммуникаций не существует'
            )
        return area

    @classmethod
    def process_house_binds(cls, house_id):
        areas = Area.objects(house__id=house_id).distinct('id')
        for area in areas:
            groups = get_area_house_groups(area, house_id)
            cls.objects(area__id=area).update(set___binds__hg=groups)

    def _area_denormalize(self):
        area = Area.objects(pk=self.area.id).get()
        self.area._type = area._type
        self.area.house = MeterEmbeddedHouse(
            id=area.house.id,
            address=area.house.address,
        )
        self.area.number = area.number
        self.area.str_number = area.str_number
        self.area.order = area.order
        self.area.gis_uid = area.gis_uid

    def _order_denormalize(self):
        order = [
            METER_ORDER_BY_TYPE.get(x)
            for x in self._type
            if METER_ORDER_BY_TYPE.get(x)
        ]
        order = order[0] if order else 00
        self.order = self.area.order * 10000 + order * 10

    def _check_readings_change(self):
        old_meter_data = Meter.objects(
            pk=self.pk
        ).as_pymongo().only('readings').first()
        old_data = {
            (r['period'], tuple(r['values']), tuple(r['deltas']))
            for r in old_meter_data['readings']
        }
        new_data = {
            (r.period, tuple(r.values), tuple(r.deltas))
            for r in self.readings
        }
        return old_data == new_data

    def _denormalize_area_communication_bond(self):
        """ Если изменилась привязка или модель новая и привязка присутсвует """

        # Указана привязка, но либо менялась, либо модель новая
        if self.communication and self._is_triggers(['communication']):
            area = self._get_area_model_by_communication()
            for cm in area.communications:
                if cm.id == self.communication:
                    cm.is_bonded = True
                    area.save()
                    return
        # Привязка не указана, при этом она изменилась (значит удалена)
        elif not self.communication and self._is_key_dirty('communication'):
            area = Area.objects(
                pk=self.area.id,
                communications__id=self.old_communication
            ).first()
            if not area:
                raise MeterDataValidationError(
                    'Такого ввода коммуникаций не существует'
                )
            for cm in area.communications:
                if cm.id == self.old_communication:
                    cm.is_bonded = False
                    area.save()
                    return

    def _find_empty_communication(self, area, meters_pairs):
        for cm in area.communications:
            if cm.is_bonded or not cm.is_active:
                continue

            if self._type[0] in meters_pairs[cm.meter_type]:
                query = {
                    'area._id': self.area.id,
                    'communication': cm.id,
                    'reverse': self.reverse,
                    'is_deleted': {'$ne': True},
                    '$or': [
                        {'working_finish_date': {'gte': datetime.now()}},
                        {'working_finish_date': None}
                    ]
                }
                potential_meters = self.__class__.objects(__raw__=query).count()
                if not potential_meters:
                    self.communication = cm.id
                    return

        raise MeterDataValidationError(
            'Не найдено свободных коммуникационных '
            'вводов при автоматическом поиске.'
        )

    def _before_save(self):
        """
        Проверка правомерности установки счетчика на стояк
        (соответствие типа и количества приборов)
        """

        # Соотвествие типов счетчиков и стояков
        meters_pairs = {
            'cold_water': ('ColdWaterAreaMeter',),
            'hot_water': ('HotWaterAreaMeter',),
            'electricity': ('ElectricOneRateAreaMeter',
                            'ElectricTwoRateAreaMeter',
                            'ElectricThreeRateAreaMeter'),
            'heat': (
                'HeatAreaMeter',
                'HeatDistributorAreaMeter'
            ),
            'gas': ('GasAreaMeter',)
        }
        all_meter_types = [y for x in meters_pairs.values() for y in x]
        # Если есть попытка подключения счетчика к стояку
        area = self._get_area_model_by_communication()
        if not self.communication:
            self._find_empty_communication(area, meters_pairs)

        # Информация о стояке
        communication_input = next(
            x for x in area.communications if x.id == self.communication
        )
        q = Q(area__id=self.area.id, is_deleted__ne=True)
        if self.pk:
            q &= Q(communication=self.communication) | Q(id=self.pk)
        else:
            q &= Q(communication=self.communication)
        meters = Meter.objects(q).only(
            'id',
            '_type',
            'reverse',
            'communication',
            'working_finish_date'
        )

        # Текущий счетчик
        if self.pk:
            current_meter = meters.filter(id=self.id)
            if current_meter:
                current_meter = current_meter.get()
        else:
            current_meter = None
        # Блок проверок, если счетчик сохраняется впервые
        if not current_meter and not self._type:
            raise MeterDataValidationError(
                'Не передан тип счетчика для присоединения к стояку'
            )
        if not current_meter and self.reverse is None:
            raise MeterDataValidationError(
                'Не передано направление работы счетчика'
            )
        if not current_meter and not self.working_start_date:
            raise MeterDataValidationError(
                'Не передано начало ввода в эксплуатацию счетчика'
            )
        # Если при сохранении передается поле привязки к коммуникации,
        # но оно такое же как и было, то нет смысла делать проверку, т.к.
        # привязка не меняется. Только если меняется привязка
        # или счетчик новый
        if (not current_meter) \
                or (not current_meter.communication == self.communication):
            # Установленные счетчики исключая текущий
            q = Q(communication=self.communication, area__id=self.area.id)
            if self.pk:
                q &= Q(id__ne=self.pk)
            exists_meters = meters.filter(q)
            # Проверка типа сохраняемого счетчика и стояка
            if self._type:
                meter_type = [x for x in self._type if x in all_meter_types]
            else:
                # Получаем тип счетчика
                meter_type = current_meter._type
                meter_type = [x for x in meter_type if x in all_meter_types]
            if not meter_type:
                raise MeterDataValidationError(
                    'Тип счетчика отсутствует или неверен'
                )
            if meter_type[0] not in meters_pairs[communication_input.meter_type]:
                raise MeterDataValidationError(
                    'Нельзя установить данный тип счетчика'
                )

            # Проверка количества уже установленных и обратных сч-ов
            # Если не передано направление работы
            if self.reverse is not None:
                reverse = self.reverse
            else:
                reverse = current_meter.reverse
            # Дата ввода в эксплуатацию
            if self.working_start_date:
                start_date = self.working_start_date
            else:
                start_date = current_meter.working_start_date

            if exists_meters:
                # Делим счетчики по типам
                reverse_meters = [x.working_finish_date
                                  for x in exists_meters
                                  if x.reverse is True]
                not_reverse_meters = [x.working_finish_date
                                      for x in exists_meters
                                      if x.reverse is False]
                # Счетчики у которых не указана дата окончания эксплуатации
                # будет указывать на запрет установки нового
                if all((None in reverse_meters, None in not_reverse_meters)):
                    raise MeterDataValidationError(
                        'Нельзя установить больше счетчиков'
                    )
                else:
                    # Нужно убедиться, что дата начала работы нового
                    # счетчика меньше окончания старого и что не превышен
                    # лимит установок счетчиков.
                    # Если устанавливаемый счетчик прямой:
                    if reverse is False:
                        # Если есть счетчики, которые не имеют
                        # дату окончания
                        if None in not_reverse_meters:
                            raise MeterDataValidationError(
                                'Нельзя установить счетчик пока '
                                'действует старый'
                            )
                        # Если дата нового счетчика не новее
                        # окончания старых
                        if [
                            True for f_date in not_reverse_meters
                            if f_date >= start_date
                        ]:
                                raise MeterDataValidationError(
                                    'Нельзя установить счетчик пока '
                                    'действует старый'
                                )
                    elif reverse is True:
                        # Если есть счетчики, которые не имеют
                        # дату окончания
                        if None in reverse_meters:
                            raise MeterDataValidationError(
                                'Нельзя установить счетчик пока '
                                'действует старый'
                            )
                        # Если дата нового счетчика не новее
                        # окончания старых
                        if [
                            True for f_date in reverse_meters
                            if f_date >= start_date
                        ]:
                            raise MeterDataValidationError(
                                'Нельзя установить счетчик пока '
                                'действует старый'
                            )

    @classmethod
    def get_binds_query(cls, binds_permissions, raw: bool = False):
        """
        Метод для преобразования переданной привязки в нужный для модели вид
        :param raw: если нужен в виде словоря
        :param binds_permissions: переданные привязки
        :return: dict, Q
        """
        result = super().get_binds_query(binds_permissions, raw)
        if raw:
            result.update({
                '_type': 'AreaMeter',
                'is_deleted': {'$ne': True}
            })
            return result
        else:
            return result & Q(_type='AreaMeter', is_deleted__ne=True)


class AdapterEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    _type = ListField(StringField(
        choices=('DisabledAdapter', 'GprsAdapter', 'CsdAdapter')
    ))
    model = StringField(
        null=True,
        choices=GPRS_ADAPTER_MODELS_CHOICES,
        verbose_name='Модель адаптера (модема)',
    )
    phone_number = StringField(null=True, verbose_name='номер телефона модема')
    sim_number = StringField(null=True, verbose_name='номер симкарты')
    app_number = StringField(null=True, verbose_name='номер приложения')
    account_number = StringField(
        null=True,
        verbose_name='номер лицевого счета мобильного оператора'
    )
    adapter_id = StringField(null=True, verbose_name='ID модема')
    tcp_port = IntField(null=True, verbose_name='Port модема')
    tuned = BooleanField(
        default=False,
        verbose_name='Настроен ли адаптер'
    )
    gprs_operator = StringField(
        choices=GPRS_OPERATORS_CHOICES,
        verbose_name='Мобильный оператор GPRS',
        null=True
    )


class ConnectionSchemaEmbedded(EmbeddedDocument):
    """
    Схема подключения
    """
    available_hot_water_supply = (('opened', 'открытая'),
                                  ('closed', 'закрытая'))
    pipe_count = (('x2', '2-х трубная'),
                  ('x4', '4-х трубная'),
                  ('x3', '3-х трубная'))

    autonomous = (
        ('dependent', 'зависимая'),
        ('independent', 'независимая')
    )

    circulation = (('with_circulation', 'с циркуляцией'),
                   ('without_circulation', 'без циркуляции'))

    pipe_count = StringField(
        null=True,
        choices=pipe_count,
        verbose_name='количество труб'
    )
    autonomous = StringField(
        null=True,
        choices=autonomous,
        verbose_name='зависимая/независимая'
    )
    circulation = StringField(
        null=True,
        choices=circulation,
        verbose_name='признак циркуляции'
    )
    available_hot_water_supply = StringField(
        null=True,
        choices=available_hot_water_supply,
        verbose_name='наличие ГВС'
    )


class SeasonEmbedded(EmbeddedDocument):
    # TODO: возможные варианты поля и то, что должно уходить на FE
    REPORT_METER_FIELDS = (
        ('time', 'Tи'),
        ('NS', 'НС'),
        ('M1', 'M1'),
        ('M2', 'M2'),
        ('dM_1', 'dM(M1-M2)'),
        ('T1', 'T1'),
        ('T2', 'T2'),
        ('dT', 'dT'),
        ('P1', 'P1'),
        ('P2', 'P2'),
        ('Qo', 'Qотопл'),

        ('M3', 'M3'),
        ('M4', 'M4'),
        ('dM_2', 'dM(M3-M4)'),
        ('V3', 'V3'),
        ('V4', 'V4'),
        ('dV', 'dV(излив)'),
        ('Vp', 'Vподпит'),
        ('T3', 'T3'),
        ('T4', 'T4'),
        ('Qg', 'Qгвс.общ'),
        ('Q_1', 'Qгвс.изл'),
        ('Q_2', 'Qтех.гвс'),
        ('Q', 'Qобщ.от+гвс'),
    )
    sensors = DictField()
    formulas = DictField()


class SeasonsMappingsEmbedded(EmbeddedDocument):
    winter = EmbeddedDocumentField(SeasonEmbedded)
    summer = EmbeddedDocumentField(SeasonEmbedded)


class HeatSystemEmbedded(EmbeddedDocument):
    """
    Тепловая система
    """
    name = StringField()
    mappings = EmbeddedDocumentField(
        SeasonsMappingsEmbedded,
        verbose_name='Соответствия датчиков в зависимости от сезона'
    )


class SeasonChangeEmbedded(EmbeddedDocument):
    season = StringField(choices=(('winter', 'зима'), ('summer', 'лето')))
    date = DateTimeField()


class EquipInfoEmbedded(EmbeddedDocument):
    EQUIP_INFO_VARIABLES = []
    for i in ('M', 'V'):
        for j in range(1, 6):
            EQUIP_INFO_VARIABLES.append('%s%d' % (i, j))
    title = StringField(verbose_name='заголовок строки')
    var_name = StringField(choices=EQUIP_INFO_VARIABLES,
                           verbose_name='Соответствует переменной')
    flowmeter = StringField(choices=FLOWMETER_TYPE,
                            verbose_name='Тип расходомера')
    g_min = StringField(verbose_name='Хар-ка датчика мин')
    g_max = StringField(verbose_name='Хар-ка датчика макс')
    T_conversion = StringField(choices=T_CONVERSIONS,
                               verbose_name='Термопреобразовтель')
    V_conversion = StringField(choices=V_CONVERSIONS,
                               verbose_name='Преобразователь давлений')


class ExpancesEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    central_heating = ListField(
        FloatField(),
        verbose_name='Центальное отопление',
        max_length=2,
        min_length=2
    )
    central_vent = FloatField(
        null=True,
        verbose_name='Центральная вентиляция'
    )
    tech_heating = FloatField(
        null=True,
        verbose_name='Техническое отопление'
    )
    tech_hot_water_supply = FloatField(
        null=True,
        verbose_name='Техническое горячее водоснабжение'
    )
    avg_tech_hot_water_supply = FloatField(
        null=True,
        verbose_name='Среднее техническое горячее водоснабжение'
    )
    hot_water_supply = ListField(
        FloatField(),
        verbose_name='Горячее водоснабжение',
        max_length=2,
        min_length=2
    )


class HouseMeter(BasicMeter, Document, BindedModelMixin):
    """ Домовой счетчик """

    house = EmbeddedDocumentField(MeterEmbeddedHouse)
    digit_capacity = FloatField(
        required=True,
        default=9999999.999,
        verbose_name='Разрядность счётчика',
    )
    adapter = EmbeddedDocumentField(
        AdapterEmbedded,
        verbose_name=''
    )
    mounting = StringField(
        null=True,
        verbose_name='Расположение счетчика'
    )
    install_at = DateTimeField(
        null=True,
        verbose_name='дата установки прибора учета'
    )
    started_at = DateTimeField(
        null=True,
        verbose_name='дата ввода в эксплуатацию прибора учета'
    )
    checked_at = DateTimeField(
        null=True,
        verbose_name='дата проведения поверки прибора учета'
    )
    temperature_sensor = BooleanField(
        null=True,
        verbose_name='Наличие датчика температуры'
    )
    pressure_sensor = BooleanField(
        null=True,
        verbose_name='Наличие датчика давления'
    )

    description_control = StringField(
        null=True,
        verbose_name='Описание до обновления'
    )
    serial_number_control = StringField(
        null=True,
        verbose_name='Заводской номер до обновления'
    )
    reference = BooleanField(
        null=True,
        verbose_name="Справочный счетчик"
    )

    ####
    # HouseHeatMeter
    ####
    meter_model = StringField(
        null=True,
        choices=METER_MODEL,
        verbose_name='В связи с автоматизацией добавляем'
    )
    flowmeter_type = StringField(
        null=True,
        choices=FLOWMETER_TYPE,
        verbose_name='Тип расходомера'
    )
    sphere_application = StringField(
        null=True,
        choices=SPHERE_APPLICATION,
        verbose_name='Сфера применения'
    )
    connection_schema = EmbeddedDocumentField(
        ConnectionSchemaEmbedded,
        default=ConnectionSchemaEmbedded,
        verbose_name='Схема соединения',
    )
    temperature_chart = StringField(
        null=True,
        regex=r'^\d{2,3}/\d{2,3}$',
        verbose_name='т. график',
    )
    pressure_transformer = StringField(
        null=True,
        choices=V_CONVERSIONS,
        verbose_name='',
    )
    winter_calc_formula = StringField(
        null=True,
        verbose_name='формула подсчета теплоты'
    )
    summer_calc_formula = StringField(
        null=True,
        verbose_name='=/='
    )
    code_uute = StringField(
        null=True,
        verbose_name='узел учета тепловой энергии'
    )
    heat_systems = EmbeddedDocumentListField(
        HeatSystemEmbedded,
        verbose_name='Тепловая система'
    )
    season_change = EmbeddedDocumentListField(
        SeasonChangeEmbedded,
        verbose_name='Смена времени года')
    equip_info = EmbeddedDocumentListField(
        EquipInfoEmbedded,
        verbose_name='Дополнительная информация по счетчику'
    )

    address = StringField(
        null=True,
        verbose_name='Обслуживаемый адрес'
    )
    expances = EmbeddedDocumentField(
        ExpancesEmbedded,
        default=ExpancesEmbedded,
        verbose_name='договорные нагрузки'
    )

    tolerance_dt = IntField(default=3, verbose_name='допустимое отклонение dT')
    allowable_unbalance_mass = IntField(
        default=2,
        verbose_name='допустимый небаланс масс'
    )
    _binds = EmbeddedDocumentField(
        HouseGroupBinds,
        verbose_name='Привязки к группе домов'
    )

    def save(self, *args,  **kwargs):

        if self.connection_schema:
            self.connections_validation()
        self._check_history_denormalize()
        if not self.pk:
            self._order_denormalize()
        if not kwargs.get('ignore_meter_validation'):
            self._validate_working_period()
        if not self._binds:
            self._binds = HouseGroupBinds(hg=self._get_house_binds())
        self.restrict_changes()
        result = super().save(*args, **kwargs)

        return result

    def _get_house_binds(self):
        return get_house_groups(self.house.id)

    @classmethod
    def process_house_binds(cls, house_id):
        groups = get_house_groups(house_id)
        cls.objects(
            _type='HouseMeter',
            house__id=house_id,
        ).update(set___binds__hg=groups)

    AVAILABLE_HOT_WATER_SUPPLY = dict(
        opened='открытая',
        closed='закрытая',
    )
    PIPE_COUNT = {
        'x2': '2-х трубная',
        'x4': '4-х трубная',
        'x3': '3-х трубная',
    }
    CIRCULATION = dict(
        with_circulation='с циркуляцией',
        without_circulation='без циркуляции',
    )

    def connections_validation(self):
        c_n = self.connection_schema
        if c_n.pipe_count == self.PIPE_COUNT['x2']:
            if (
                    c_n.available_hot_water_supply
                    == self.AVAILABLE_HOT_WATER_SUPPLY['closed']
                    and c_n.circulation == self.CIRCULATION['with_circulation']
            ):
                raise Exception("Проверьте схему подключения!")
        elif c_n.pipe_count == self.PIPE_COUNT['x3']:
            if c_n.circulation:
                raise Exception("Проверьте схему подключения!")
        elif c_n.pipe_count == self.PIPE_COUNT['x4']:
            if c_n.circulation != self.CIRCULATION['with_circulation']:
                raise Exception("Проверьте схему подключения!")

    @classmethod
    def get_binds_query(cls, binds_permissions, raw: bool = False):
        """
        Метод для преобразования переданной привязки в нужный для модели вид
        :param raw: если нужен в виде словоря
        :param binds_permissions: переданные привязки
        :return: dict, Q
        """
        result = super().get_binds_query(binds_permissions, raw)
        if raw:
            result.update({
                '_type': 'HouseMeter',
                'is_deleted': {'$ne': True}
            })
            return result
        else:
            return result & Q(_type='HouseMeter', is_deleted__ne=True)
