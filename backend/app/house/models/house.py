import re
import itertools
from datetime import datetime

from bson import ObjectId
from mongoengine import Document, EmbeddedDocument, \
    FloatField, StringField, IntField, DynamicField, EmbeddedDocumentField, \
    ObjectIdField, BooleanField, DateTimeField, ListField, DictField, \
    EmbeddedDocumentListField, ValidationError
from mongoengine.queryset.visitor import Q

from app.caching.models.denormalization import DenormalizationTask
from lib.address import construct_house_number, construct_house_address, \
    get_location_by_fias, get_street_location_by_fias
from processing.models.billing.base import HouseGroupBinds, BindedModelMixin
from processing.models.billing.common_methods import get_house_groups, \
    get_areas_range
from processing.models.billing.crm.constants import ACTIVE_STATUSES
from processing.models.billing.embeddeds.geo_point import GeoPoint
from processing.models.billing.embeddeds.house import DenormalizedHouseWithFias
from processing.models.billing.fias import Fias
from processing.models.billing.files import Files
from processing.models.billing.provider.main import Provider
from processing.models.billing.sytem_message import SystemMessage
from processing.models.billing.business_type import BusinessType
from processing.models.choices import ACCRUAL_SECTOR_TYPE_CHOICES
from processing.models.house_choices import ALL_COMMUNITY_SYSTEMS_CHOICES, \
    WELL_TYPES_CHOICES, BUILDING_DESIGN_TYPES_CHOICES, RESOURCE_TYPES_CHOICES, \
    HEATING_TYPES_CHOICES, HOT_WATER_SUPPLY_TYPES_CHOICES, \
    COLD_WATER_SUPPLY_TYPES_CHOICES, SEWERAGE_TYPES_CHOICES, \
    POWER_SUPPLY_TYPES_CHOICES, GAS_SUPPLY_TYPES_CHOICES, \
    VENTILATION_TYPES_CHOICES, STORM_SEWAGE_TYPES_CHOICES, \
    BOOT_RECEIVE_VALVE_PLACEMENTS_CHOICES, ENERGY_EFFICIENCY_CLASS_CHOICES, \
    AREA_LOCATIONS_CHOICES, WATER_SUPPLY_ZONES_CHOICES, \
    PROTOCOL_CATEGORIES_CHOICES, PROTOCOL_RESULTS_CHOICES, \
    HOUSE_ENGINEERING_STATUS_CHOICES, HOUSE_PORCH_INTERCOM_CHOICES, \
    HousePorchIntercomType, HOUSE_CATEGORIES_CHOICES, HOUSE_TYPES_CHOICES, \
    STRUCTURE_ELEMENTS_CHOICES, EQUIPMENT_ELEMENTS_CHOICES, \
    PRINT_BILLS_TYPE_CHOICES, WATER_TYPE_CHOICES
from utils.crm_utils import provider_can_tenant_access

AREA_TYPES = {
    'П': 'ParkingArea',
    'Ж': 'LivingArea',
    'Н': 'NotLivingArea'
}

FIAS_TOP_LEVEL_CODES = {
    'c2deb16a-0330-4f05-821f-1d09c93331e6': 'Москва',  # Санкт - Петербург город
    'c20180d9-ad9c-46d1-9eff-d60bc424592a': 'Москва',  # Коми республика
    'ed36085a-b2f5-454f-b9a9-1c9a678ee618': 'Москва',  # Вологодская область
    '6d1ebb35-70c6-4129-bd55-da3969658f5d': 'Москва',  # Ленинградская область
    '88cd27e2-6a8a-4421-9718-719a28a0a088': 'Москва',  # Нижегородская область
    'd00e1013-16bd-4c09-b3d5-3cb09fc54bd8': 'Москва',  # Краснодарский край
    '5e465691-de23-4c4e-9f46-f35a125b5970': 'Москва',  # Орловская область
    '29251dcf-00a1-4e34-98d4-5c47484a36d4': 'Москва',  # Московская область
    '92b30014-4d52-4e2e-892d-928142b924bf': 'Екатеринбург',  # Свердловская обл.
}

SETL_GROUP_DEVELOPER = [
    '5745c65a61faf4001ec9a0eb',  # ООО "Сетл Сити"
    '62bd5cb4c421840016b132f1',  # ООО "Альянс Сити Строй"
    '63c94fee8f353000358cd742',  # ООО "СЗ "Сэтл-Лиговский"
]


class HouseValidationError(ValidationError):
    pass


class Lift(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    desc = StringField(null=True, verbose_name='Описание лифта')
    number = StringField(null=True, verbose_name='Номер лифта')
    capacity = IntField(null=True, verbose_name='Грузоподъемность')
    started_at = DateTimeField(null=True, verbose_name='')
    climb_rate = FloatField(null=True, verbose_name='Скорость подъема')
    well_type = StringField(
        null=True,
        choices=WELL_TYPES_CHOICES,
        verbose_name='Шахта лифта'
    )
    stop_number = IntField(null=True, verbose_name='Количество остановок')
    manufacturer = StringField(
        null=True,
        verbose_name='Наименование завода изготовителя'
    )
    has_freq_reg = BooleanField(
        null=True,
        verbose_name='Наличие частотного регулирования дверей/привода'
    )
    deadline_years = IntField(
        null=True,
        verbose_name='Предельный срок эксплуатации'
    )
    modernization_date = DateTimeField(
        null=True,
        verbose_name='Год модернизации'
    )
    norm_durability = IntField(
        null=True,
        verbose_name='Нормативный срок службы'
    )


class BuildingDesign(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    type = StringField(
        choices=BUILDING_DESIGN_TYPES_CHOICES,
        verbose_name='Тип проекта'
    )
    series = StringField(verbose_name='Серия проекта')


class HouseTechPassport(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")

    project = EmbeddedDocumentField(
        BuildingDesign,
        verbose_name='Проект здания'
    )
    build_date = DateTimeField(verbose_name='Дата постройки')
    durability = IntField(min_value=0, verbose_name='Срок службы здания')
    deterioration = IntField(
        min_value=0,
        max_value=100,
        verbose_name='Общий износ здания, %'
    )
    count_floor = IntField(min_value=0, verbose_name='Количество этажей')
    count_floor_min = IntField(
        min_value=0,
        verbose_name='Количество этажей, наименьшее'
    )
    count_floor_max = IntField(
        min_value=0,
        verbose_name='Количество этажей, наибольшее'
    )
    count_porch = IntField(
        min_value=0,
        verbose_name='Количество подъездов'
    )
    count_stair = IntField(min_value=0, verbose_name='Количество лестниц')
    count_section = IntField(min_value=0, verbose_name='Количество секций')
    count_mansard = IntField(min_value=0, verbose_name='Количество мансард')
    count_door_shelter = IntField(
        min_value=0,
        verbose_name='Количество металлических дверей в убежищах'
    )
    area_total = FloatField(
        null=True,
        min_value=0,
        verbose_name='Общая площадь дома'
    )
    area_mop_stair = FloatField(
        min_value=0,
        verbose_name='Лестничные марши и площадки'
    )
    area_mop_lobby = FloatField(
        min_value=0,
        verbose_name='Коридоры мест общего пользования'
    )
    area_tech_floor = FloatField(
        min_value=0,
        verbose_name='Технический этаж (между этажами)'
    )
    area_tech_underfloor = FloatField(
        min_value=0,
        verbose_name='Техническое подполье (технический подвал)'
    )
    area_tech_other = FloatField(
        min_value=0,
        verbose_name='Иные технические помещения '
                     '(мастерские, электрощитовые, водомерные узлы и др.)'
    )
    area_basement = FloatField(min_value=0, verbose_name='Площадь подвалов')
    area_shelter = FloatField(min_value=0, verbose_name='Площадь убежищ')
    area_garret = FloatField(
        min_value=0,
        default=0,
        verbose_name='Площадь чердаков'
    )
    area_other = FloatField(
        min_value=0,
        verbose_name='Площадь прочих помещений общего пользования '
                     '(клубы, детские комнаты, помещения консьержей, '
                     'колясочные и т.д.)'
    )
    is_landmark = BooleanField(
        default=False,
        verbose_name='Принадлежность к памятнику архитектуры'
    )


class HouseResourceInput(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    type = StringField(
        choices=RESOURCE_TYPES_CHOICES,
        verbose_name='Вид ресурса',
    )
    meter = ObjectIdField(
        verbose_name='Оборудование вводов в многоквартирный дом '
                     'инженерных систем для подачи ресурсов, '
                     'необходимых для предоставления коммунальных услуг, '
                     'приборами учета'
    )
    inputs_number = IntField(
        min_value=0,
        verbose_name='Количество вводов в многоквартирный дом '
                     'инженерных систем для подачи ресурсов'
    )
    inputs_formula = DynamicField(
        verbose_name='Места и количество вводов в многоквартирный дом '
                     'инженерных систем для подачи ресурсов'
    )
    inputs_placements = ListField(
        StringField(),
        verbose_name='Места ввода в многоквартирный дом '
                     'инженерных систем для подачи ресурсов'
    )


class HouseEquipmentInfo(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")

    class BaseEquipmentInfo(EmbeddedDocument):
        meta = {'allow_inheritance': True}

        id = ObjectIdField(db_field="_id")

        has_automatic = BooleanField(
            default=False,
            verbose_name='установлена система автоматического сбора показаний'
        )
        filling_length = IntField(min_value=0, verbose_name='длина розлива')
        risers_number = IntField(min_value=0, verbose_name='количество стояков')
        risers_cellar_length = IntField(
            min_value=0,
            verbose_name='длина стояков в подвалах'
        )
        risers_apartment_length = IntField(
            min_value=0,
            verbose_name='длина стояков в квартирах'
        )
        wiring_apartment_length = IntField(
            min_value=0,
            verbose_name='длина разводки в квартирах'
        )

    class HeatEquipmentInfo(BaseEquipmentInfo):
        id = ObjectIdField(db_field="_id")
        type = StringField(
            choices=HEATING_TYPES_CHOICES,
            default='none',
            verbose_name='тип отопления'
        )
        radiators_stairwell_number = IntField(
            min_value=0,
            verbose_name='количество радиаторов на лестничных клетках'
        )
        radiators_apartment_number = IntField(
            min_value=0,
            verbose_name='количество радиаторов в квартирах'
        )
        heat_insulation_area = IntField(
            min_value=0,
            verbose_name='площадь теплоизоляции'
        )
        steel_heaters_number = IntField(
            min_value=0,
            verbose_name='калориферы стальные'
        )
        convectors_number = IntField(min_value=0, verbose_name='конвекторы')
        valves_number = IntField(min_value=0, verbose_name='вентили')
        bolt_valves_number = IntField(
            min_value=0,
            verbose_name='запорно-регулирующая арматура'
        )
        catch_valves_number = IntField(
            min_value=0,
            verbose_name='задвижки'
        )
        threeway_valves_number = IntField(
            min_value=0,
            verbose_name='трехходовые краны'
        )
        elevators_number = IntField(min_value=0, verbose_name='элеваторы')
        duct_numbers = IntField(min_value=0, verbose_name='короба')
        heat_nodes_number = IntField(
            min_value=0,
            verbose_name='количество теплоцентров'
        )

    class HWSEquipmentInfo(BaseEquipmentInfo):
        id = ObjectIdField(db_field="_id")
        type = StringField(
            choices=HOT_WATER_SUPPLY_TYPES_CHOICES,
            default='none',
            verbose_name='тип водоснабжения'
        )
        has_control = BooleanField(
            default=False,
            verbose_name='установлен узел управления')
        catch_valves = ListField(StringField(), verbose_name='задвижки')
        valves_cellar_number = IntField(
            min_value=0,
            verbose_name='количество вентилей в подвалах'
        )
        cork_cranes_cellar = IntField(
            min_value=0,
            verbose_name='количество пробковых кранов в подвалах'
        )

    class CWSEquipmentInfo(BaseEquipmentInfo):
        id = ObjectIdField(db_field="_id")
        type = StringField(
            choices=COLD_WATER_SUPPLY_TYPES_CHOICES,
            default='none',
            verbose_name='тип водоснабжения'
        )
        has_control = BooleanField(
            default=False,
            verbose_name='установлен узел управления'
        )
        brass_valves = ListField(
            StringField(),
            verbose_name='вентили латунные'
        )
        measuring_number = IntField(
            min_value=0,
            verbose_name='количество водомерных узлов'
        )
        valves_cellar_number = IntField(
            min_value=0,
            verbose_name='количество вентилей в подвалах'
        )

    class SewerageEquipmentInfo(BaseEquipmentInfo):
        id = ObjectIdField(db_field="_id")
        type = StringField(
            choices=SEWERAGE_TYPES_CHOICES,
            default='none',
            verbose_name='Тип канализации'
        )
        pipes_cellar_length = IntField(
            min_value=0,
            verbose_name='Длина канализационных труб в подвалах'
        )
        revision_caps_number = IntField(
            min_value=0,
            verbose_name='Количество крышек ревизий'
        )

    class PowerEquipmentInfo(EmbeddedDocument):
        id = ObjectIdField(db_field="_id")

        type = StringField(
            choices=POWER_SUPPLY_TYPES_CHOICES,
            default='none',
            verbose_name='Тип электроснабжения'
        )
        has_control = BooleanField(verbose_name='установлен узел управления')
        has_automatic = BooleanField(
            verbose_name='установлена система автоматического сбора показаний'
        )
        has_control_device = BooleanField(
            verbose_name='вводно-распределительное устройство'
        )
        common_panels = IntField(
            min_value=0,
            verbose_name='количество групповых щитков в подвале и '
                         'на лестничной клетке'
        )
        power_panels = IntField(
            min_value=0,
            verbose_name='количество силовых щитов'
        )
        public_lighting_supply = FloatField(
            min_value=0,
            verbose_name='длина сетей коммунального освещения'
        )
        lifts_pumps_supply = FloatField(
            min_value=0,
            verbose_name='длина сетей питания лифтов и электронасосов'
        )
        address_signs = IntField(
            min_value=0,
            verbose_name='количество номерных знаков'
        )
        lamps_daylight = IntField(
            min_value=0,
            verbose_name='количество светильников дневного света'
        )
        lamps_incandescent = IntField(
            min_value=0,
            verbose_name='количество светильников с лампами накаливания'
        )
        lamps_mercury = IntField(
            min_value=0,
            verbose_name='количество светильников с лампами ДРЛ'
        )
        lamps_outdoor = IntField(
            min_value=0,
            verbose_name='количество уличных осветительных приборов'
        )
        switchers = IntField(
            min_value=0,
            verbose_name='количество выключателей'
        )

    class NaturalGasEquipmentInfo(EmbeddedDocument):
        id = ObjectIdField(db_field="_id")
        type = StringField(
            choices=GAS_SUPPLY_TYPES_CHOICES,
            default='none',
            verbose_name='Тип газоснабжения'
        )
        total_length = FloatField(
            min_value=0,
            verbose_name='длина сетей газоснабжения'
        )

    class VentilationEquipmentInfo(EmbeddedDocument):
        id = ObjectIdField(db_field="_id")
        type = StringField(
            choices=VENTILATION_TYPES_CHOICES,
            default='none',
            verbose_name='Тип вентиляции'
        )

    class StormSewageEquipmentInfo(EmbeddedDocument):
        id = ObjectIdField(db_field="_id")
        type = StringField(
            choices=STORM_SEWAGE_TYPES_CHOICES,
            default='none',
            verbose_name='Тип водостока'
        )

    class GarbageEquipmentInfo(EmbeddedDocument):
        id = ObjectIdField(db_field="_id")
        total_volume = FloatField(
            min_value=0,
            verbose_name='объем мусороприемных камер'
        )
        total_area = FloatField(
            min_value=0,
            verbose_name='площадь мусороприемных камер'
        )
        trunks_number = IntField(
            min_value=0,
            verbose_name='количество стволов'
        )
        valves_number = IntField(
            min_value=0,
            verbose_name='количество приемо-загрузочных клапанов'
        )
        valves_placement = StringField(
            choices=BOOT_RECEIVE_VALVE_PLACEMENTS_CHOICES,
            verbose_name='тип клапана'
        )

    class LiftEquipmentInfo(EmbeddedDocument):
        id = ObjectIdField(db_field="_id")
        total_number = IntField(
            min_value=0,
            verbose_name='общее количество'
        )
        foldaway_number = IntField(
            min_value=0,
            verbose_name='в том числе с раздвижными дверями'
        )
        dooropen_number = IntField(
            min_value=0,
            verbose_name='в том числе с открывающими дверями'
        )
        intercoms_number = IntField(
            min_value=0,
            verbose_name='ПЗУ (переговорно-замочное устройство) '
                         'или кодовый замок'
        )
        lifts = ListField(
            EmbeddedDocumentField(Lift),
            verbose_name='Сведения о лифтах дома'
        )

    class OtherEquipment(EmbeddedDocument):
        id = ObjectIdField(db_field="_id")
        desc = StringField(
            verbose_name='характеристика и '
                         'функциональное назначение оборудования'
        )
        title = StringField(verbose_name='наименование оборудования')
        placement = StringField(verbose_name='место расположения оборудования')

    cws = EmbeddedDocumentField(CWSEquipmentInfo, verbose_name='ХВС')
    hw = EmbeddedDocumentField(HWSEquipmentInfo, verbose_name='ГВС')
    gas = EmbeddedDocumentField(NaturalGasEquipmentInfo, verbose_name='ГС')
    heat = EmbeddedDocumentField(HeatEquipmentInfo, verbose_name='ТС')
    power = EmbeddedDocumentField(
        PowerEquipmentInfo,
        verbose_name='Электроснабжение'
    )
    garbage = EmbeddedDocumentField(
        GarbageEquipmentInfo,
        verbose_name='Приемо-загрузочные клапаны'
    )
    sewerage = EmbeddedDocumentField(
        SewerageEquipmentInfo,
        verbose_name='Канализация'
    )
    lift_info = EmbeddedDocumentField(
        LiftEquipmentInfo,
        verbose_name='Лифтовое оборудование'
    )
    storm_seweage = EmbeddedDocumentField(
        StormSewageEquipmentInfo,
        verbose_name='Водостоки'
    )
    ventilation = EmbeddedDocumentField(
        VentilationEquipmentInfo,
        verbose_name='Вентиляция'
    )
    other = ListField(
        EmbeddedDocumentField(OtherEquipment),
        verbose_name='иное оборудование'
    )


class HouseGroundArea(EmbeddedDocument):
    """
    Земельный участок, на котором расположен многоквартирный дом
    """

    class HardSurfaces(EmbeddedDocument):
        """
        Твердые покрытия
        """
        # Типы твердых покрытий
        SurfaceType = (
            ('thoroughfares', 'проезды'),
            ('pavements', 'тротуары'),
            ('other', 'прочие'),
        )

        # SCHEMA = {x: SquareMeters for x in SurfaceType.get_all()}
        thoroughfares = FloatField(min_value=0)
        pavements = FloatField(min_value=0)
        other = FloatField(min_value=0)

    class Gardening(EmbeddedDocument):
        """
        Сведения об элементах озеленения и благоустройства
        """

        # Типы зеленых насаждений
        PlantationType = (
            ('squares', 'скверы'),
            ('lawn', 'газон с деревьями'),
            ('other', 'прочие'),
        )

        # SCHEMA = {x: PositiveFloat for x in PlantationType.get_all()}
        squares = FloatField(min_value=0)
        lawn = FloatField(min_value=0)
        other = FloatField(min_value=0)

    class Playgrounds(EmbeddedDocument):
        """
        Детские площадки
        """

        # Типы площадок
        PlaygroundType = (
            ('children', 'детские'),
            ('sports', 'спортивные'),
            ('other', 'прочие'),
        )

        # SCHEMA = {x: SquareMeters for x in PlaygroundType.get_all()}
        children = FloatField(min_value=0)
        sports = FloatField(min_value=0)
        other = FloatField(min_value=0)

    inventory = StringField(verbose_name='Инвентарный номер земельного участка')
    cadastral = StringField(verbose_name='Кадастровый номер земельного участка')
    area_tech = FloatField(
        min_value=0,
        default=0,
        verbose_name='Общая площадь земельного участка '
                     'по данным технической инвентаризации'
    )
    area_survey = FloatField(
        min_value=0,
        verbose_name='Общая площадь земельного участка по данным межевания'
    )
    area_actual = FloatField(
        min_value=0,
        verbose_name='Общая площадь земельного участка '
                     'по фактическому пользованию, всего'
    )
    area_built = FloatField(min_value=0, verbose_name='Застроенная площадь')
    area_unbuilt = FloatField(min_value=0, verbose_name='Незастроенная площадь')
    area_surfaces = EmbeddedDocumentField(
        HardSurfaces,
        verbose_name='Площади твердых покрытий'
    )
    area_gardening = EmbeddedDocumentField(
        Gardening,
        verbose_name='Озеленение и благоустройство'
    )
    area_playgrounds = EmbeddedDocumentField(
        Playgrounds,
        verbose_name='Площади площадок'
    )


class HouseRepairWorkInfo(EmbeddedDocument):
    """
    Сведения о проведенных капитальных и аварийных ремонтных работах МКД
    """
    # TODO Required(Any(StructureElement, EquipmentElement)),
    #  тип конструктивных элементов или элементов оборудования
    elem = DynamicField()
    type = DynamicField(null=True)  # TODO RepairWork.WorkGroup, вид ремонта
    cost = IntField()  # TODO Required(Money, default=0), стоимость работ
    operations = StringField(verbose_name='перечень выполненных работ')
    fin_sources = StringField(verbose_name='источники финансирования работ')


class HouseTerritory(EmbeddedDocument):
    """
    Придомовая территория
    """
    REGISTER = False
    HAS_ID = False

    # Типы покрытия придомовой территории
    HouseTerritoryType = (
        ('improved', 'с усовершенствованным покрытием'),
        ('unimproved', 'с неусовершенствованным покрытием'),
        ('unsurfed', 'без покрытия'),
        ('lawn', 'газоны'),
        ('other', 'прочие'),
    )

    class CommunityPropertyObject(EmbeddedDocument):
        """
        Объект общего имущества
        """

        comm_type = StringField(choises=ALL_COMMUNITY_SYSTEMS_CHOICES)
        area_total = FloatField(
            min_value=0,
            default=0,
            verbose_name='площадь объекта'
        )

    comm_property = EmbeddedDocumentListField(
        CommunityPropertyObject,
        verbose_name='объекты общего имущества'
    )
    total_area = FloatField(
        min_value=0,
        verbose_name='площадь придомовой территории'
    )
    improved = FloatField(min_value=0)
    unimproved = FloatField(min_value=0)
    unsurfed = FloatField(min_value=0)
    lawn = FloatField(min_value=0)
    other = FloatField(min_value=0)


class InspectionReport(EmbeddedDocument):
    """
    Сведения о конструктивных элементах многоквартирного дома
    """
    meta = {'allow_inheritance': True}

    inspector = ObjectIdField(
        verbose_name='сведения об организации '
                     'или физическом лице, производящем осмотр'
    )
    # TODO Optional(StructureElement or EquipmentReport)
    elem = StringField(
        verbose_name='тип конструктивных элементов или тип оборудования'
    )
    date = DateTimeField(verbose_name='дата акта проведенного осмотра')
    wear = IntField(
        min_value=0,
        verbose_name='процент износа по результатам осмотра'
    )
    desc = StringField(verbose_name='результаты осмотра')
    doc = DynamicField(verbose_name='документ-основание')


# Два одинаковых класса добавлены, поскольку в
# старых моделях поля "elem" аналогичных классов имеют разные choices
class HouseStructureReport(InspectionReport):
    elem = StringField(
        choices=STRUCTURE_ELEMENTS_CHOICES,
        verbose_name='тип конструктивных элементов или тип оборудования'
    )


class HouseEquipmentReport(InspectionReport):
    elem = StringField(
        choices=EQUIPMENT_ELEMENTS_CHOICES,
        verbose_name='тип конструктивных элементов или тип оборудования'
    )


class HouseEnergyEfficiency(EmbeddedDocument):
    """
    Энергоэффективность
    """

    # TODO оригинальное поле называется "class",
    #  видимо придется поправить старую модель
    _class = StringField(
        choices=ENERGY_EFFICIENCY_CLASS_CHOICES,
        default='c',
        verbose_name='Класс энергоэффективности'
    )

    degreedays = IntField(
        verbose_name='Градусо-сутки отопительного периода по средней '
                     'многолетней продолжительности отопительного периода'
    )
    examined_at = DateTimeField(
        verbose_name='Дата проведения энергетического обследования'
    )


class HousePowerConsumption(EmbeddedDocument):
    """
    Характеристики максимального энергопотребления здания
    """

    class InstalledPowerHeat(EmbeddedDocument):
        """
        Установленная тепловая мощность
        """

        PowerHeatType = (
            ('heating', 'на отопление'),
            ('hot_water_supply', 'на горячее водоснабжение'),
            ('airheat_curtains', 'на воздушно-тепловые завесы'),
            ('forced_circulation', 'на принудительная вентиляция')
        )

        heating = FloatField(min_value=0)
        hot_water_supply = FloatField(min_value=0)
        airheat_curtains = FloatField(min_value=0)
        forced_circulation = FloatField(min_value=0)

    class InstalledPowerElectrical(EmbeddedDocument):
        """
        Установленная электрическая мощность
        """

        PowerElectricalType = (
            ('common_lighting', 'на общедомовое освещение'),
            ('lift_equipment', 'на лифтовое оборудование'),
            ('ventilation', 'на вентиляцию'),
            ('others', 'прочая электрическая мощность')
        )

        common_lighting = FloatField(min_value=0)
        lift_equipment = FloatField(min_value=0)
        ventilation = FloatField(min_value=0)
        others = FloatField(min_value=0)

    class DailyConsumption(EmbeddedDocument):
        """
        Среднесуточный расход
        """

        DailyConsumptionType = (
            ('gas', 'природного газа'),
            ('cws', 'холодной воды'),
            ('hws', 'горячей воды'),
            ('el', 'электричества')
        )

        gas = FloatField(min_value=0)
        cws = FloatField(min_value=0)
        hws = FloatField(min_value=0)
        el = FloatField(min_value=0)

    class MaxHourlyConsumption(EmbeddedDocument):
        """
        Удельный максимальный часовой расход
        """

        HourlyConsumptionType = (
            ('heat', 'на отопление'),
            ('vent', 'на вентиляцию')
        )

        heat = FloatField(min_value=0)
        vent = FloatField(min_value=0)

    class AvgHourlyConsumption(EmbeddedDocument):
        """
        Среднечасовой за отопительный период расход тепла
        """

        hws = FloatField(min_value=0)

    heat_feat = FloatField(
        min_value=0,
        verbose_name='Удельная тепловая характеристика здания'
    )
    installed_power_heat = EmbeddedDocumentField(
        InstalledPowerHeat,
        verbose_name='Установленая тепловая мощность'
    )
    installed_power_electrical = EmbeddedDocumentField(
        InstalledPowerElectrical,
        verbose_name='Установленая электрическая мощность'
    )
    consumption_hourly_max = EmbeddedDocumentField(
        MaxHourlyConsumption,
        verbose_name='Удельный максимальный часовой расход'
    )
    consumption_hourly_avg = EmbeddedDocumentField(
        AvgHourlyConsumption,
        verbose_name='Среднечасовой расход'
    )
    consumption_daily_avg = EmbeddedDocumentField(
        DailyConsumption,
        verbose_name='Среднесуточный расход'
    )


class HousePassport(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    number = StringField(verbose_name='Уникальный номер дома')
    address = StringField(verbose_name='Почтовый адрес многоквартирного дома')
    tech_info = EmbeddedDocumentField(
        HouseTechPassport,
        verbose_name='Технические характеристики'
    )
    resources = ListField(
        EmbeddedDocumentField(HouseResourceInput),
        verbose_name='Места ввода в дом инженереных систем для подачи ресурсов'
    )
    equipment = EmbeddedDocumentField(
        HouseEquipmentInfo,
        verbose_name='Сведения о признании дома аварийным'
    )
    alarm_info = StringField(verbose_name='')
    ground_area = EmbeddedDocumentField(
        HouseGroundArea,
        verbose_name='Земельный участок'
    )
    works_repair = ListField(
        EmbeddedDocumentField(HouseRepairWorkInfo),
        verbose_name='Сведения о проведенных работах МКД'
    )
    house_territory = EmbeddedDocumentField(
        HouseTerritory,
        verbose_name='Придомовая территория'
    )
    structure_reports = ListField(
        EmbeddedDocumentField(HouseStructureReport),
        verbose_name='Сведения о конструктивных элементах'
    )
    equipment_reports = ListField(
        EmbeddedDocumentField(HouseEquipmentReport),
        verbose_name='Сведения'
    )
    energy_efficiency = EmbeddedDocumentField(
        HouseEnergyEfficiency,
        verbose_name='Энергоэффективность дома'
    )
    power_consumption = EmbeddedDocumentField(
        HousePowerConsumption,
        verbose_name='Энергопотребление дома'
    )


class WaterZoneEmbedded(EmbeddedDocument):
    lower = IntField(null=True)
    upper = IntField(null=True)


class StandPipeEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    x = ListField(
        IntField(),
        null=True,
        verbose_name='координаты по оси абсцисс, '
                     'отражающие положение стояка в квартирограмме'
    )
    y = ListField(
        IntField(),
        null=True,
        verbose_name='координаты по оси ординат, '
                     'отражающие положение стояка в квартирограмме'
    )
    desc = StringField(null=True, verbose_name='описание')
    number = StringField(null=True, verbose_name='номер')
    located_at = StringField(
        null=True,
        choices=AREA_LOCATIONS_CHOICES,
        verbose_name='место расположения'
    )
    water_zone = StringField(
        null=True,
        choices=WATER_SUPPLY_ZONES_CHOICES,
        verbose_name='принадлежность к зоне водоснабжения'
    )
    service_type = ObjectIdField(
        null=True,
        verbose_name='вид услуги (ХВС, ГВС, ЦО и т.п.)'
    )
    type = StringField(
        null=True,
        choices=WATER_TYPE_CHOICES,
        verbose_name='тип стояка'
    )


class Porch(EmbeddedDocument):
    id = ObjectIdField(db_field="_id", default=ObjectId)

    min_floor = IntField(default=1, verbose_name='номер нижнего этажа')
    max_floor = IntField(default=1, verbose_name='номер верхнего этажа')
    lifts = EmbeddedDocumentListField(Lift, verbose_name='информация о лифтах')
    has_lift = BooleanField(default=False, verbose_name='Наличие лифта')
    start_num_floor = IntField(
        default=1,
        verbose_name='Номер этажа, от которого начинается отсчет'
    )
    standpipes = EmbeddedDocumentListField(
        StandPipeEmbedded,
        default=[StandPipeEmbedded()],
        verbose_name='информация о стояках'
    )
    water_zone_limits = EmbeddedDocumentField(
        WaterZoneEmbedded,
        default=WaterZoneEmbedded,
        verbose_name='границы зон водоснабжения'
    )
    number = IntField(verbose_name='Номер', default=1)
    start_num_area = IntField(
        verbose_name='Номер квартиры, от которой начинается отсчет'
    )
    has_appz = BooleanField(
        default=False,
        verbose_name='Наличие автоматической противопожарной защиты'
    )
    pzu = StringField(
        choices=HOUSE_PORCH_INTERCOM_CHOICES,
        default=HousePorchIntercomType.ELECTRIC,
        verbose_name='Наличие/тип ПЗУ'
    )
    has_chute = BooleanField(default=True, verbose_name='')
    area_count = IntField(null=True, verbose_name='Кол-во квартир')
    build_date = DateTimeField(null=True, verbose_name='дата постройки')


class HouseServiceBindEmbeddedSector(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")

    sector_code = StringField(choices=ACCRUAL_SECTOR_TYPE_CHOICES)
    permissions = DictField()  # flags (c, r, u, d)


class HouseEmbededServiceBind(EmbeddedDocument):
    id = ObjectIdField(db_field="_id", default=ObjectId)

    provider = ObjectIdField(required=True,
                             verbose_name='Привязанная организация')
    date_start = DateTimeField(verbose_name='Дата начала привязки')
    date_end = DateTimeField(null=True, verbose_name='Дата окончания привязки')
    sectors = EmbeddedDocumentListField(
        HouseServiceBindEmbeddedSector,
        verbose_name='Права на направления',
    )
    areas_range = StringField(
        verbose_name='Диапазон квартир, обслуживаемых организацией')
    business_type = ObjectIdField(
        verbose_name='Вид деятельности в отношении к дому')
    is_active = BooleanField(default=True, verbose_name='Привязка активна')
    is_public = BooleanField(
        null=True,
        verbose_name='Открыта для публичного просмотра'
    )
    is_full = BooleanField(
        verbose_name='Все ли помещения дома соответствуют привязке')
    sync_responsibles_from_udo = BooleanField(
        null=True,
        verbose_name='Синхронизировать ли ответственных из УО'
    )
    group = ObjectIdField(null=True,
                          verbose_name='Идентификатор группы провайдеров')

    def is_actual(self, date_on: datetime = None) -> bool:
        """Актуальная (на дату) привязка?"""
        if not date_on:
            date_on = datetime.now()
        elif isinstance(date_on, str):  # frontend?
            date_on = datetime.strptime(date_on, '%Y-%m-%dT%H:%M:%S')

        if not self.date_start or self.date_start > date_on:
            return False
        if self.date_end and self.date_end < date_on:
            return False

        return True

    def has_sector(self, code: str, *permission_s: str) -> bool:
        """Имеет разрешения для направления платежа?"""
        for embedded in self.sectors or []:
            assert isinstance(embedded, HouseServiceBindEmbeddedSector)
            if embedded.sector_code == code:
                # {'c': True, 'r': True, 'u': True, 'd': True}
                if all(embedded.permissions.get(perm) is True
                        for perm in permission_s):
                    return True

        return False


class HouseEmbeddedProtocolDoc(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")

    number = StringField(required=True, verbose_name='номер протокола')
    date = DateTimeField(verbose_name='дата протокола')
    # TODO Использование старых файлов
    file = EmbeddedDocumentField(Files, verbose_name='Список сканов протокола')
    description = StringField()
    category = StringField(null=True, choices=PROTOCOL_CATEGORIES_CHOICES)
    result = StringField(choices=PROTOCOL_RESULTS_CHOICES)


class SettingsEmbedded(EmbeddedDocument):
    is_managment = BooleanField(
        verbose_name='Управление личными кабинетами жителей дома',
        default=True
    )
    is_reg_open = BooleanField(
        verbose_name='Самостоятельная регистрация кабинетов жителями',
        default=True
    )
    auto_close_meters_cw = BooleanField(
        verbose_name='Закрывать ли автоматически квартирные счётчики ХВ',
        default=False
    )
    auto_close_meters_hw = BooleanField(
        verbose_name='Закрывать ли автоматически квартирные счётчики ГВ',
        default=False
    )
    auto_close_meters_ee = BooleanField(
        verbose_name='Закрывать ли автоматически квартирные счётчики эл/эн',
        default=False
    )
    auto_close_meters_he = BooleanField(
        verbose_name='Закрывать ли автоматически квартирные счётчики тепл/эн',
        default=False
    )
    auto_close_meters_g = BooleanField(
        verbose_name='Закрывать ли автоматически квартирные счётчики газа',
        default=False
    )
    requests_provider = ObjectIdField(null=True)


class DeveloperEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    str_name = StringField(null=True)
    legal_form = StringField(null=True)
    name = StringField(null=True)


class EmbeddedInfo(EmbeddedDocument):
    title = StringField(null=True, verbose_name='заголовок')
    text = StringField(null=True, verbose_name='текст сообщения')
    author = StringField(null=True, verbose_name='автор сообщения')


class EmbeddedManagerContract(EmbeddedDocument):
    id = ObjectIdField(db_field='_id', default=ObjectId)
    number = StringField(null=True)
    date = DateTimeField(null=True)
    gis_uid = StringField(null=True, verbose_name="Идентификатор ГИС ЖКХ")
    file_id = ObjectIdField(null=True, verbose_name="Идентификатор файла")


class HeatingContractExpancesEmbedded(EmbeddedDocument):
    """
    Договорные нагрузки
    """
    id = ObjectIdField(db_field='_id')
    central_heating = DynamicField()
    hot_water_supply = DynamicField()
    # central_heating = ListField(
    #     FloatField(null=True),
    #     verbose_name='Центальное отопление',
    # )
    central_vent = FloatField(verbose_name='Центральная вентиляция')
    tech_heating = FloatField(verbose_name='Техническое отопление')
    tech_hot_water_supply = FloatField(
        verbose_name='Техническое горячее водоснабжение',
    )
    avg_tech_hot_water_supply = FloatField(
        verbose_name='Среднее техническое горячее водоснабжение',
    )
    # hot_water_supply = ListField(
    #     FloatField(null=True),
    #     verbose_name='Горячее водоснабжение',
    # )


class HeatingContractEmbedded(EmbeddedDocument):
    """
    Договор о теплоснабжении
    """
    id = ObjectIdField(db_field='_id')
    boiler = ObjectIdField(verbose_name='Котельная')
    number = StringField(verbose_name='Номер')
    date = DateTimeField(verbose_name='Дата договора')
    expanses = EmbeddedDocumentField(
        HeatingContractExpancesEmbedded,
        verbose_name='Договорные нагрузки',
    )
    worker = StringField(verbose_name='Ответственный работник')
    inspector = StringField(verbose_name='Инспектор')
    doc = StringField(verbose_name='Договор-основание')


class GisMeteringEmbedded(EmbeddedDocument):
    """Параметры передачи показаний ПУ в ГИС ЖКХ"""
    start_day = IntField(verbose_name="Начало периода ввода показаний ИПУ")
    end_day = IntField(verbose_name="Окончание периода ввода показаний ИПУ")

    collective = BooleanField(default=False,
        verbose_name="Выгружать показания ОДПУ?")


class GisDataEmbedded(EmbeddedDocument):
    """Данные ГИС ЖКХ дома"""
    # uid = StringField(null=True, verbose_name="Уникальный номер в ГИС ЖКХ")

    fias = StringField(null=True, verbose_name="Идентификатор ФИАС в ГИС ЖКХ")

    doc_day = IntField(verbose_name="Срок выставления ПД за услуги")
    pay_day = IntField(verbose_name="Срок внесения платы за услуги")

    metering = EmbeddedDocumentField(GisMeteringEmbedded,
        null=True, verbose_name="Параметры передачи показаний ПУ")


class ShortCourtAddressEmbedded(EmbeddedDocument):
    """Краткий адрес суда"""
    id = ObjectIdField(db_field='_id', required=True)
    address = StringField(verbose_name='Адрес суда', required=True)


class JudgeEmbedded(EmbeddedDocument):
    """Сотрудник суда."""
    id = ObjectIdField(db_field='_id', required=True)
    name = StringField(verbose_name='Имя судьи', required=True)

    @property
    def json(self):
        return {k: str(v) for k, v in self.to_mongo().items()}


class AttachedCourtEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id', required=True)
    name = StringField(required=True)
    court_address = EmbeddedDocumentField(
        ShortCourtAddressEmbedded,
        required=False
    )
    court_type = StringField(required=True)
    judge = EmbeddedDocumentField(
        JudgeEmbedded,
        required=False
    )


class House(Document, BindedModelMixin):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'House',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            '_binds.hg',
        ],
    }

    _binds = EmbeddedDocumentField(
        HouseGroupBinds,
        verbose_name='Привязки к группе домов',
    )
    harvested_region_standard = FloatField(
        null=True,
        verbose_name='Уборочная площадь з.участка по нормативу'
    )
    area_garret = FloatField(default=0, verbose_name='Площадь чердаков')
    heating_type = StringField(null=True, verbose_name='Тип отопления')
    parking_count = IntField(
        null=True,
        verbose_name='Количество парко-мест в доме'
    )
    fias_street_guid = StringField(verbose_name='Ссылка на AOGUID в ФИАС')
    area_not_living = FloatField(
        null=True,
        verbose_name='Площадь нежилых помещений'
    )
    lift_count = IntField(null=True, verbose_name='Количество лифтов')
    area_average_apartment = FloatField(
        null=True,
        verbose_name='Средняя площадь квартиры'
    )
    harvested_region_actual = FloatField(
        null=True,
        verbose_name='Уборочная площадь з.участка фактическая'
    )
    heating_contract = EmbeddedDocumentField(
        HeatingContractEmbedded,
        null=True,
        verbose_name='Договор теплоснабжения',
    )
    harvested_stairs_standard = FloatField(
        null=True,
        verbose_name='Уборочная площадь лестниц по нормативу'
    )
    area_roof = FloatField(null=True, verbose_name='Площадь крыши')
    apartment_count = IntField(null=True, verbose_name='Количество квартир')
    short_address = StringField(verbose_name='Короткий адрес')
    harvested_stairs_actual = FloatField(
        null=True,
        verbose_name='Уборочная площадь лестниц фактическая'
    )
    info = EmbeddedDocumentField(
        EmbeddedInfo,
        default=EmbeddedInfo,
        verbose_name='Информация'
    )
    settings = EmbeddedDocumentField(
        SettingsEmbedded,
        default=lambda: SettingsEmbedded(),
        verbose_name='Настройки'
    )
    bulk = StringField(verbose_name='корпус. ФИАС - BUILDNUM')
    has_plumbing = BooleanField(verbose_name='Водопровод', default=True)
    build_date = DateTimeField(null=True, verbose_name='Дата постройки')
    management_contract = EmbeddedDocumentField(
        document_type=EmbeddedManagerContract,
        verbose_name='Договор управления'
    )
    area_basements = FloatField(null=True, verbose_name='Площадь подвалов')
    address = StringField(verbose_name='Адрес дома')
    setl_home_address = StringField(
        verbose_name='Код адреса со стороны Setl Home'
    )
    area_parking = FloatField(null=True, verbose_name='Площадь паркинга дома')
    has_sewage = BooleanField(null=True, verbose_name='Канализация')
    area_total = FloatField(default=0, verbose_name='Общая площадь')
    area_tech = FloatField(default=0, verbose_name='Площадь технического этажа')
    street = StringField(verbose_name='Улица дома')
    type = StringField(
        choices=HOUSE_TYPES_CHOICES,
        verbose_name='Тип строения',
    )
    area_heating = FloatField(
        null=True,
        verbose_name='Отапливаемая площадь дома'
    )
    service_binds = EmbeddedDocumentListField(
        HouseEmbededServiceBind,
        verbose_name='Привязки организаций к домам'
    )
    structure = StringField(
        default='',
        verbose_name='строение. ФИАС - STRUCNUM'
    )
    porches = EmbeddedDocumentListField(
        Porch,
        default=[Porch()],
        verbose_name='Подъезды'
    )
    capital_repair_date = DateTimeField(
        null=True,
        verbose_name='Дата капитального ремонта'
    )
    service_date = DateTimeField(
        null=True,
        verbose_name='Дата ввода в эксплуатацию'
    )
    area_living = FloatField(null=True, verbose_name='Жилая площадь')
    stair_count = IntField(null=True, verbose_name='Кол-во лестниц')
    fias_house_guid = StringField(
        default='',
        verbose_name='Ссылка на HOUSEGUID в ФИАС'
    )
    number = StringField(verbose_name='номер. ФИАС - HOUSENUM')
    stove_type = StringField(null=True, verbose_name='Тип плит')
    zip_code = StringField(verbose_name='Индекс')
    default_rooms_height = FloatField(
        null=True,
        verbose_name='Высота помещения по умолчанию'
    )
    floor_count = StringField(null=True, verbose_name='Количество этажей')
    kladr = StringField(verbose_name='Код улицы (кладр)')
    fias_addrobjs = ListField(
        StringField(),
        verbose_name='Родительские addrobj'
    )
    street_only = StringField(verbose_name='Улица дома')
    point = EmbeddedDocumentField(
        GeoPoint,
        default=GeoPoint,
        verbose_name='Гео-координата'
    )
    fund_id = StringField(verbose_name='Идентификатор МКД в Реформе ЖКХ')
    OKTMO = StringField(verbose_name='Код ОКТМО')
    overhaul_code = StringField(
        verbose_name='Код многоквартирного дома в региональной '
                     'программе капитального ремонта'
    )
    fund_type = IntField(
        null=True,
        verbose_name='Способ формирования фонда капитального ремонта'
    )
    area_total_auto = FloatField(
        null=True,
        verbose_name='Общая полезная площадь, '
                     'калькулируемая при сохранении квартиры'
    )
    offsets_updated_at = DateTimeField(
        null=True,
        verbose_name='Когда последний раз '
                     'пересчитывали офсеты по дому'
    )
    area_overall = FloatField(null=True, verbose_name='Полная площадь дома')
    hws_type = StringField(verbose_name='Тип ГВС', default='central')
    developer = EmbeddedDocumentField(
        DeveloperEmbedded,
        default=DeveloperEmbedded,
        verbose_name='Дом принадлежит застройщику'
    )
    passport = EmbeddedDocumentField(
        HousePassport,
        verbose_name='Электронный паспорт дома'
    )
    is_allowed_meters = BooleanField(
        null=True,
        verbose_name='Возможна установка ПУ'
    )
    category = StringField(
        choices=HOUSE_CATEGORIES_CHOICES,
        verbose_name='Категория дома',
    )
    protocol_doc = EmbeddedDocumentListField(HouseEmbeddedProtocolDoc)
    _sb_cached = DynamicField(null=True, verbose_name='')
    _redmine = DynamicField(null=True, verbose_name='')

    from_csv = BooleanField(default=False, verbose_name='Импортирован из файла')

    engineering_status = StringField(
        null=True,
        verbose_name='Состояние здания',
        choices=HOUSE_ENGINEERING_STATUS_CHOICES
    )
    is_cultural_heritage = BooleanField(default=False)
    cadastral_number = StringField()
    gis_uid = StringField(
        null=True,
        verbose_name='Уникальный номер дома в ГИС ЖКХ'
    )
    gis_fias = StringField(null=True, verbose_name='ФИАС в ГИС ЖКХ')
    is_deleted = BooleanField()

    gis_metering_start = IntField(
        verbose_name="Начало периода ввода показаний ПУ",
    )
    gis_metering_end = IntField(
        verbose_name="Окончание периода ввода показаний ПУ",
    )

    gis_pay_doc_day = IntField(
        verbose_name="Срок выставления ПД за жилое помещение и КУ",
    )
    gis_pay_day = IntField(
        verbose_name="Срок внесения платы за жилое помещение и КУ",
    )

    gis_collective = BooleanField(
        verbose_name="Выгружать в ГИС ЖКХ показания ОДПУ дома?"
    )

    attached_courts = EmbeddedDocumentListField(
        AttachedCourtEmbedded,
        verbose_name='Привязанные суды к дому'
    )

    print_bills_type = StringField(
        required=False,
        choices=PRINT_BILLS_TYPE_CHOICES,
        verbose_name='Параметр печати квитанций',
    )

    @classmethod
    def by_fias(cls, fias_guid: str, provider_id: ObjectId = None) -> 'House':

        query: dict = {'$or': [
            {'fias_house_guid': fias_guid},
            {'gis_fias': fias_guid},
        ],
            'is_deleted': {'$ne': True},
        }
        if provider_id is not None:
            query['service_binds.provider'] = provider_id

        return cls.objects(__raw__=query).first()

    @classmethod
    def bound_providers(cls, house_id: ObjectId) -> list:
        """
        Идентификаторы связанных с домом провайдеров
        """
        house: House = cls.objects.only('service_binds').with_id(house_id)

        return [*house.provider_binds(True)]

    def provider_binds(self, is_active: bool = None,
                       is_started: bool = None,
                       is_not_finished: bool = None) -> dict:
        """
        Управляющие и обслуживающие организации дома

        :param is_active: False/True - не/действующие, None - все
        :param is_started: True - начавшие управление или обслуживание дома
        :param is_not_finished: True - продолжающие управление или обслуживание
        """
        now = datetime.now() if (is_started or is_not_finished) else None

        return {bind.provider: bind for bind in self.service_binds
                if bind.provider  # есть всегда?
                and (is_active is None or bind.is_active == is_active)
                and (is_started is None or
                     not bind.date_start or bind.date_start < now)
                and (is_not_finished is None or
                     not bind.date_end or now < bind.date_end)}

    @property
    def gis_timezone(self):
        """Временная зона для ГИС"""
        for fias_code in FIAS_TOP_LEVEL_CODES:
            if fias_code in self.fias_addrobjs:
                return FIAS_TOP_LEVEL_CODES[fias_code]

    @property
    def fias_guid(self) -> str:
        """
        Идентификатор дома по ФИАС
        """
        _fias_guid = self.gis_fias or self.fias_house_guid  # редко не совпадают
        assert _fias_guid, f"Не найден ФИАС-идентификатор дома {self.id}"

        return _fias_guid

    @classmethod
    def process_house_binds(cls, house_id):
        groups = get_house_groups(house_id)
        cls.objects(pk=house_id).update(set___binds__hg=groups)

    @staticmethod
    def _load_addrobj(aoguid):
        query = dict(AOGUID=aoguid, LIVESTATUS='1')
        fias_street = Fias.objects(**query).as_pymongo().first()
        return fias_street

    @staticmethod
    def _create_fias_address(street_aoguid):
        """
        Формирование пути до привязываемого дома.
        Например Лиговский проспект -> Санкт-Петербург.
        :returns street_path, fias_addrobjs
        """

        path = [street_aoguid]
        find_parent = (
            lambda guid:
            Fias.objects(AOGUID=guid, LIVESTATUS='1').as_pymongo().first()
        )
        next_parent = find_parent(street_aoguid['PARENTGUID'])
        path.insert(0, next_parent)
        while next_parent.get('PARENTGUID'):
            next_parent = find_parent(next_parent['PARENTGUID'])
            path.insert(0, next_parent)
        # Формируем путь по ФИАСу от улицы до города
        street_path = (
            ', '.join(el['SHORTNAME'] + ' ' + el['OFFNAME'] for el in path)
            if path
            else ''
        )
        fias_addrobjs = [el['AOGUID'] for el in filter(None, path)]
        return street_path, fias_addrobjs

    def _delete_empty_fields(self):
        """
        Удаляет пустые объекты, которые создаёт монгоэнжин
        """
        if self.porches:
            for porch in self.porches:
                if (
                        porch.water_zone_limits.upper is None
                        and porch.water_zone_limits.lower is None
                ):
                    delattr(porch, 'water_zone_limits')

    @staticmethod
    def _str_to_datetime(date_string, default_date):
        """
        Преобразует даты в текстовом виде с фронтенда в datetime объект
        """
        if isinstance(date_string, datetime):
            return date_string
        elif date_string:
            return datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%S')
        else:
            return default_date

    def _denormalize_binds_to_actors(self, denormalization_task):
        """
        Данный метод пересоздает направления и основную организацию
        в акторах ЛКЖ
        """
        if denormalization_task:
            from app.caching.tasks.denormalization import \
                denormalize_house_sectors_to_cabinets
            denormalize_house_sectors_to_cabinets.delay(
                self.id,
                denormalization_task.id,
            )
        actor_provider_id = self.get_default_provider_by_sectors()
        if not actor_provider_id:
            return
        from app.auth.models.actors import Actor
        from utils.crm_utils import provider_can_tenant_access
        from processing.models.billing.provider.embeddeds import \
            ActorProviderEmbedded
        provider = Provider.objects(
            pk=actor_provider_id,
        ).only(
            'str_name',
            'inn',
        ).first()
        client_access = provider_can_tenant_access(actor_provider_id)
        Actor.objects(owner__house__id=self.id).update(
            provider=ActorProviderEmbedded(
                id=actor_provider_id,
                str_name=provider.str_name,
                inn=provider.inn,
                client_access=client_access,
            )
        )

    def save(self, *args, **kwargs):
        self.restrict_changes()
        is_service_binds_changed = self._is_triggers(['service_binds'])

        # Порядок важен!!!
        self._delete_empty_fields()
        self.process_address_changed()

        cabinet_demormalization_task = None
        if is_service_binds_changed:
            self._denormalize_developer()
            if not self._created:
                cabinet_demormalization_task = \
                    self._save_cabinet_denormalization_task()
        self._create_house_binds()
        self._check_binds_fullness()

        if self._created:
            is_service_binds_changed = True
        address_changed = False
        if not self._created and 'address' in self._changed_fields:
            address_changed = True
        setl_home_address_changed = False
        if self._is_triggers(['setl_home_address']):
            if self.get_developer_from_setl_home():
                setl_home_address_changed = True
            else:
                self.setl_home_address = None

        result = super().save(*args, **kwargs)
        rebuild_fias_tree = False
        if address_changed:
            self.foreign_denormalize()
            rebuild_fias_tree = True
        if is_service_binds_changed:
            self._denormalize_binds_to_actors(cabinet_demormalization_task)
            self._create_nonexistent_areas()
            self.check_areas_binds()
            self._recreate_binds()
            rebuild_fias_tree = True

            # TODO: удалить после релиза новой аутентификации
            self._send_service_binds_updated_message()
        if rebuild_fias_tree:
            self.build_fias_tree()
        if setl_home_address_changed:
            self.change_setl_home_address()

        return result

    def _save_cabinet_denormalization_task(self):
        task = DenormalizationTask(
            model_name='House',
            field_name='service_binds.sectors',
            obj_id=self.id,
            func_name='denormalize_house_sectors_to_cabinets',
            kwargs={
                'house_id': self.id,
            },
        )
        task.save()
        return task

    def foreign_denormalize(self):
        from app.caching.tasks.denormalization import \
            foreign_denormalize_data
        foreign_denormalize_data.delay(
            model_from=House,
            field_name='address',
            object_id=self.pk,
        )

    def _create_house_binds(self):
        """Создание привязки дома, если нет"""

        if not self._binds:
            if not self.pk and self._created:
                self.id = ObjectId()
                # После присвоения ID пометится как не новый, исправим это
                self._created = True
            self._binds = HouseGroupBinds(hg=self._get_house_binds())

    def get_service_binds(self, provider, date=None, sector_codes=None):
        """
        Выделение привязок дома по заданым условиям
        :provider: Provider,  Организация, привязки которой
        :date: datetime,  Момент времени, на который нужно разобрать привязки,
                          datetime.now() по умолчанию
        :sector_codes: list, set,  # Список кодов для которых необходимо
                                 учитывать привязки, по умолчанию все возможные
        """

        date = date or datetime.now()
        service_binds = self.service_binds or []
        sector_codes = set(sector_codes or []) or set(itertools.chain(*[
            [sector['sector_code'] for sector in service_bind['sectors']]
            for service_bind in service_binds
        ]))

        for _filter in (
                lambda service_bind: service_bind['provider'] == provider.id,
                lambda service_bind: service_bind['is_active'],
                lambda service_bind: (
                        service_bind['date_start']
                        < date and (not service_bind.get('date_end')
                                    or service_bind['date_end'] > date)
                ),
                lambda service_bind: (
                        any([
                            sector['sector_code'] in sector_codes
                            for sector in service_bind['sectors']
                        ])
                )
        ):
            service_binds = list(filter(_filter, service_binds))

        return list(service_binds)

    def parse_bindings_to_areas(self, service_binds, area_types=None) -> list:
        """
        Разбор привязок дома в список со строковыми номерами помещений
        :service_binds: [House.service_bind],  #
        """
        from app.area.models.area import Area

        areas = dict()
        for service_bind in service_binds:

            service_bind_query = Q(house__id=self.id, is_deleted__ne=True)
            if area_types:
                service_bind_query &= Q(_type__in=area_types)

            # Если привязка не полная - добавляем в запрос
            # конкретные номера квартир
            if not service_bind['is_full']:
                area_str_numbers = self._parse_numbers(service_bind)
                service_bind_query &= Q(str_number__in=list(area_str_numbers))

            for area in Area.objects(service_bind_query):
                areas[area.str_number] = area

        return list(areas.values())

    def _parse_numbers(self, service_bind):
        area_str_numbers = set()

        str_range = service_bind['areas_range'].upper()
        parts = str_range.replace(' ', '').split(',')

        for part in parts:
            if '-' in part:
                range_start, range_end = part.split('-')

                range_start_number = int(
                    ''.join([ch for ch in range_start if ch.isdigit()])
                )
                range_start_letter = ''.join(
                    [ch for ch in range_start if ch.isalpha()]
                )
                range_end_number = int(
                    ''.join([ch for ch in range_end if ch.isdigit()])
                )
                range_end_letter = ''.join(
                    [ch for ch in range_end if ch.isalpha()]
                )
                if range_start_letter != range_end_letter:
                    pass  # TODO raise

                # NOTE range с обратным порядком(напр. 5-4) вернет пустой список
                number_list = [
                    str(number) + range_end_letter
                    for number in range(
                        range_start_number,
                        range_end_number + 1
                    )
                ]
                for area_str_number in number_list:
                    area_str_numbers.add(area_str_number)
            else:
                area_str_numbers.add(part)
        return area_str_numbers

    def is_rural(self):

        # Если на верхнем уровне город фед. значения
        if set(self.fias_addrobjs) & {
            'c2deb16a-0330-4f05-821f-1d09c93331e6',  # Санкт - Петербург город
            '0c5b2444-70a0-4932-980c-b4dc0d3f02b5',  # Москва город
            '6fdecb78-893a-4e3f-a5ba-aa062459463b',  # Севастополь город
        }:
            return False

        # Если среди родительских fias_addrobjs встречается
        # объект с уровнем(AOLEVEL) 4(город)
        f_objects = Fias.objects(AOGUID__in=self.fias_addrobjs, LIVESTATUS=1)
        if any([fias_aobj.AOLEVEL == '4' for fias_aobj in f_objects]):
            return False

        return True

    def _attach_fias_house(self, fias_house_guid, location=None):
        if not location and fias_house_guid:
            location = get_location_by_fias(
                fias_house_guid,
                receive_geo_point=False,
            )
        if fias_house_guid:
            self.fias_house_guid = fias_house_guid
        if location:
            self.number = location.extra['house_number']
            self.bulk = location.extra['bulk']
            self.structure = location.extra['structure_num']
            self._attach_fias_addrobj(location)

    def _attach_fias_addrobj(self, location=None, force=False):
        if not location:
            location = get_location_by_fias(
                self.fias_house_guid,
                receive_geo_point=False,
            )
        self.fias_street_guid = location.fias_street_guid
        if not self.street or force:
            self.street = location.location
        self.fias_addrobjs = location.fias_addrobjs
        if not self.street_only or force:
            self.street_only = location.extra.get('street_only') or ''
        self.kladr = location.extra.get('kladr')
        self.OKTMO = location.extra.get('oktmo')

    def get_city(self):
        """ Получение города из адреса дома """
        address = []
        for fias_aouid in self.fias_addrobjs:
            fias_addr_obj = Fias.objects(AOGUID=fias_aouid,
                                         LIVESTATUS='1').only('AOLEVEL',
                                                              'OFFNAME',
                                                              'FORMALNAME',
                                                              'SHORTNAME').all()
            if fias_addr_obj:
                if fias_addr_obj[0].AOLEVEL == '1':
                    address.insert(
                        0,
                        '{} {}'.format(
                            fias_addr_obj[0].SHORTNAME,
                            fias_addr_obj[0].FORMALNAME
                        )
                    )
                elif fias_addr_obj[0].aolevel == '4':
                    address.append('{} {}'.format(
                        fias_addr_obj[0].SHORTNAME, fias_addr_obj[0].OFFNAME
                    ))
        return ', '.join(address)

    def reattach_fias(self):
        self._attach_fias_addrobj(force=True)

    def _check_binds_fullness(self):
        """ Проверяем, что привязка включает в себя все квартиры дома """

        if self._is_triggers(['service_binds']):
            for bind in self.service_binds:
                bind.is_full = self._is_full_bind(bind)

    def _get_geo_point(self):
        """ Получение координат дома на карте """
        try:
            geo_point = GeoPoint.get_geocode(self.address)
            self.point = GeoPoint(coordinates=geo_point)
        except Exception:
            self.point = GeoPoint(coordinates=GeoPoint.DEFAULT_COORDINATES)

    def _create_nonexistent_areas(self):
        """ Создание еще несуществующих квартир """

        from app.area.models.area import Area

        queries = []
        areas_numbers = set()
        for bind in self.service_binds:
            if bind.areas_range:
                queries.append(self.parse_areas_range_to_query(bind.areas_range))
                areas_numbers |= set(
                    self._parse_range_to_list(bind.areas_range)
                )

        if areas_numbers:
            raw_query = {
                'house._id': self.id,
                '$or': queries
            }
            fields = 'number', '_type'
            areas = Area.objects(__raw__=raw_query).only(*fields).as_pymongo()
            exists_areas = {
                (x['_type'][0], x['number'])
                for x in areas
            }
            not_exist_areas = areas_numbers - exists_areas
            # Создание квартир
            for area in not_exist_areas:
                new_area = Area(
                    number=area[1],
                    _type=[area[0]],
                    house=DenormalizedHouseWithFias(
                        id=self.id,
                        address=self.address,
                    )
                )
                new_area.save()

    def check_areas_range(self, provider_id: ObjectId) -> str:
        """Сформировать диапазон помещений дома"""
        service_bind: HouseEmbededServiceBind = \
            self.provider_binds(True).get(provider_id)
        assert service_bind is not None, "Дом не обслуживается организацией"

        house_areas_range: str = get_areas_range(self.id, provider_id)
        if house_areas_range != service_bind.areas_range:
            # print('HOUSE', self.id, 'PROVIDER', provider_id, 'AREAS RANGE',
            #     service_bind.areas_range, 'CHANGED', house_areas_range)
            service_bind.areas_range = house_areas_range  # is_full в save
            self.save()  # выполняется привязка помещений к организации

        return house_areas_range

    def check_areas_binds(self):
        """ Создание AreaBinds """

        from app.area.models.area import Area
        from processing.models.billing.area_bind import AreaBind

        changed = False
        for bind in self.service_binds:
            if bind.areas_range:
                raw_query = self.parse_areas_range_to_query(bind.areas_range)
            else:
                raw_query = {}
            raw_query['house._id'] = self.id
            areas = Area.objects(__raw__=raw_query).distinct('id')
            all_areas = Area.objects(house__id=self.id).distinct('id')
            area_binds = AreaBind.objects(
                area__in=all_areas,
                provider=bind.provider,
                closed=None
            ).distinct('area')
            # Добавим отсутствующие
            binds_to_create = set(areas) - set(area_binds)
            if binds_to_create:
                created = datetime.now()
                new_area_binds = [
                    AreaBind(
                        provider=bind.provider,
                        area=area,
                        created=created
                    )
                    for area in binds_to_create
                ]
                AreaBind.objects().insert(new_area_binds)
            # закроем ненужные
            binds_to_close = set(area_binds) - set(areas)
            if binds_to_close:
                AreaBind.objects(
                    area__in=binds_to_close,
                    provider=bind.provider,
                    closed=None
                ).update(set__closed=datetime.now())
            if binds_to_close or binds_to_create:
                changed = True
        return changed

    def _parse_range_to_list(self, str_range):
        """
        Разбор строкового диапазона квартир в список номеров и типов квартир
        :param str_range: строка диапазона
        """
        str_range = str_range.upper()
        invalids = []
        areas = []

        # Разбираем все диапазоны и одиночные значения в списки
        for part in str_range.replace(' ', '').split(','):
            numbers = []
            for str_number in part.split('-'):
                if not str_number:
                    numbers.append('')
                    continue

                match = re.match(r'^(\d{1,6})([ЖНП])?$', str_number)
                if not match:
                    invalids.append(part)
                    break

                number, letter = match.groups()
                # Определяем тип квартиры, исходя из полученной литеры
                _type = (
                    AREA_TYPES.get(letter.upper())
                    if letter
                    else 'LivingArea'
                )
                if not _type:
                    invalids.append(part)
                    break
                numbers.append((_type, int(number)))

            if part in invalids:
                continue

            if len(numbers) == 1:
                if numbers[0]:
                    # Конкретный номер
                    areas.append(numbers[0])
            elif len(numbers) == 2:
                if not numbers[0] or not numbers[1]:
                    invalids.append(part)
                    continue

                # Диапазон «от и до», например 5-10
                condition = (
                        numbers[0][1] > numbers[1][1]
                        or numbers[0][0] != numbers[1][0]
                )
                if condition:
                    invalids.append(part)
                    continue

                for number in range(numbers[0][1], numbers[1][1] + 1):
                    areas.append((numbers[0][0], number))
            else:
                invalids.append(part)

        if invalids:
            # Ошибка, если обнаружена хоть одна некорректная часть диапазона
            raise HouseValidationError(
                'Некорректные значения '
                'диапазона: {}'.format(', '.join(invalids))
            )
        return areas

    @staticmethod
    def parse_areas_range_to_query(str_range, path=''):
        """
        Разбор строкового диапазона квартир в mongodb-запрос
        :param str_range: строка диапазона
        :param path: префикс квартирного поля, если поиск производится
                     в чужой коллекции по денормализованному полю
        """
        str_range = str_range.upper()
        queries = []
        invalids = []

        # Формируем пути к полям
        # (по-умолчанию перфикса нет, ибо ищем в родной коллекции)
        path_dot = path + '.' if path else ''
        path_type = path_dot + '_type'
        path_number = path_dot + 'number'

        # Разбираем все диапазоны и одиночные значения в списки
        for part in str_range.replace(' ', '').split(','):
            numbers = []
            for str_number in part.split('-'):
                if not str_number:
                    numbers.append('')
                    continue

                match = re.match(r'^(\d{1,6})([ЖНП])?$', str_number)
                if not match:
                    invalids.append(part)
                    break

                number, letter = match.groups()

                # Определяем тип квартиры, исходя из полученной литеры
                _type = (
                    AREA_TYPES.get(letter.upper()) if letter else 'LivingArea'
                )
                if not _type:
                    invalids.append(part)
                    break
                numbers.append({
                    path_type: _type,
                    path_number: int(number),
                })

            if part in invalids:
                continue

            if len(numbers) == 1:
                if numbers[0]:
                    # Конкретный номер
                    queries.append(numbers[0])
            elif len(numbers) == 2:
                if not numbers[0] and not numbers[1]:
                    invalids.append(part)
                    continue

                if part.startswith('-'):
                    # Бесконечный диапазон «до», например -10
                    queries.append({
                        path_type: numbers[1][path_type],
                        path_number: {'$lte': numbers[1][path_number]},
                    })
                elif part.endswith('-'):
                    # Бесконечный диапазон «от», например 10-
                    queries.append({
                        path_type: numbers[0][path_type],
                        path_number: {'$gte': numbers[0][path_number]},
                    })
                else:
                    # Диапазон «от и до», например 5-10
                    condition = (
                            numbers[0][path_number] > numbers[1][path_number]
                            or numbers[0][path_type] != numbers[1][path_type]
                    )
                    if condition:
                        invalids.append(part)
                        continue

                    queries.append({
                        path_type: numbers[0][path_type],
                        path_number: {
                            '$gte': numbers[0][path_number],
                            '$lte': numbers[1][path_number]
                        },
                    })
            else:
                invalids.append(part)

        if invalids:
            # Ошибка, если обнаружена хоть одна некорректная часть диапазона
            raise HouseValidationError(
                'Некорректные значения '
                'диапазона: {}'.format(', '.join(invalids))
            )

        return {'$or': queries}

    def _denormalize_developer(self):
        """ Принадлежит ли дом застройщику """
        b_types_providers = {
            x.business_type: x.provider for x in self.service_binds
        }
        query = dict(id__in=list(b_types_providers), slug='dev')
        b_types = BusinessType.objects(**query).as_pymongo()
        b_types = {x['_id']: x['slug'] for x in b_types}
        if not b_types:
            if self.developer:
                self.developer = None
            return
        if len(b_types) > 1:
            raise HouseValidationError(
                'К дому привязано более одного застройщика!'
            )
        from processing.models.billing.provider.main import Provider
        pr_id = b_types_providers[list(b_types.keys())[0]]
        provider = Provider.objects(
            id=pr_id,
        ).only(
            'name',
            'legal_form',
            'str_name',
        ).as_pymongo().get()
        delattr(self, 'developer')
        self.developer = DeveloperEmbedded(
            id=provider['_id'],
            str_name=provider['str_name'],
            legal_form=provider['legal_form'],
            name=provider['name'],
        )

    def get_provider_by_business_type(self, code, date_on=None):

        b_type = BusinessType.objects(slug=code).as_pymongo().first()
        if not b_type:
            return None
        if not date_on:
            date_on = datetime.now()
        for bind in self.service_binds:
            assert isinstance(bind, HouseEmbededServiceBind)
            if bind.business_type == b_type['_id'] and \
                    bind.is_active and bind.is_actual(date_on):
                return bind.provider
        return None

    def get_provider_by_sector(self, sector, date_on=None):
        if not date_on:
            date_on = datetime.now()
        for bind in self.service_binds:
            if (
                    bind.is_active
                    and
                    self._str_to_datetime(bind.date_start, date_on)
                    <= date_on <=
                    self._str_to_datetime(bind.date_end, date_on)
            ):
                for bind_sector in bind.sectors:
                    if (
                            bind_sector.sector_code == sector
                            and bind_sector.permissions.get('c')
                    ):
                        provider = Provider.objects(
                            pk=bind.provider
                        ).only(
                            'crm_status',
                        ).as_pymongo(
                        ).first()

                        if provider.get('crm_status') in ACTIVE_STATUSES:
                            return bind.provider
        return None

    def get_default_provider_by_sectors(self, date_on=None):
        for sector in ACCRUAL_SECTOR_TYPE_CHOICES:
            result = self.get_provider_by_sector(sector[0], date_on)
            if result:
                return result
        return self.get_provider_by_business_type('udo', date_on)

    def get_sectors(self, date_on=None):
        if not date_on:
            date_on = datetime.now()
        result = set()
        for bind in self.service_binds:
            if (
                    bind.is_active
                    and (bind.date_start or date_on) <= date_on
                    and (bind.date_end or date_on) >= date_on
            ):
                result |= {s.sector_code for s in bind.sectors}
        return result

    def get_sectors_by_area_ranges(self, date_on=None):
        if not date_on:
            date_on = datetime.now()
        range_sectors = dict()
        for bind in self.service_binds:
            # Проверим, актуальна ли привязка
            date_start = self._str_to_datetime(bind.date_start, date_on)
            date_end = self._str_to_datetime(bind.date_end, date_on)
            if (
                    bind.is_active
                    and bind.areas_range
                    and date_start <= date_on <= date_end
                    and provider_can_tenant_access(bind.provider)
            ):
                range_sectors.setdefault(
                    bind.areas_range,
                    set(),
                ).update(
                    [
                        sector['sector_code']
                        for sector in bind.sectors
                    ],
                )
        return range_sectors

    @classmethod
    def find_bound_provider(cls, house_id, active_only=True, tenant=False):
        """
        Получение ID управляющей организации к которой прикреплен дом.
        Поиск среди организаций клиентво происходит по убыванию
        приоритета слагов: 'udo', 'cpr', 'cс', 'gvs'.
        Если никакая из списка не удовлетворяет слагам - берется первая.
        :param tenant - (временный параметр, необходимый при вызове метода из
        старой модели Tenant)
        """
        house = cls.objects(id=house_id).as_pymongo().first()
        # Отсеим не клиентов
        clients = {
            s['business_type']: s
            for s in (house.get('service_binds', []) if house else [])
            if cls._is_valid_client(s, active_only, tenant)
        }
        if not clients:
            return
        for client in clients.values():
            if client['provider'] == ObjectId('5c9346e443cf66002dd04daa'):
                return client['provider']

        bt_slugs = {
            x['slug']: x['_id']
            for x in BusinessType.objects.all().as_pymongo()
        }
        # Возьмем по приоритету слага
        slugs_priority = 'udo', 'cpr', 'cс', 'gvs'
        for slug in slugs_priority:
            bind = clients.get(bt_slugs[slug])
            if bind:
                return bind['provider']

        return clients[list(clients.keys())[0]]['provider']

    @staticmethod
    def _is_valid_client(service_bind, active_only, tenant):
        from utils.crm_utils import provider_can_access, \
            provider_can_tenant_access
        func = provider_can_access if not tenant else provider_can_tenant_access
        return all([
            func(service_bind['provider']),
            not active_only or service_bind['is_active']
        ])

    def _is_full_bind(self, bind):
        """ Проверяет, что привязка включает в себя все квартиры дома. """

        if not bind.areas_range:
            return True

        from app.area.models.area import Area

        house_area_count = Area.objects(house__id=self.id).count()
        raw_query = {
            'house._id': self.id,
            **self.parse_areas_range_to_query(bind.areas_range)
        }
        range_area_count = Area.objects(__raw__=raw_query).count()
        return range_area_count == house_area_count

    def _send_service_binds_updated_message(self):
        providers = set()

        old_house = House.objects(
            id=self.id
        ).only('service_binds').as_pymongo().get()

        if old_house:
            for service_bind in old_house['service_binds']:
                providers.add(service_bind['provider'])

        for service_bind in self.service_binds:
            providers.add(service_bind.provider)

        params = dict(
            _type=['ServiceBindsChangedMessage'],
            house=self.id,
            providers=list(providers)
        )
        SystemMessage(**params).save()

    def _get_house_binds(self):
        return get_house_groups(self.pk)

    def process_address_changed(self):
        csv_condition = self.from_csv and not self.fias_house_guid
        if self._is_triggers(['fias_house_guid']) and not csv_condition:
            fias_house_guid = self.fias_house_guid
            if not fias_house_guid:
                location = get_street_location_by_fias(
                    self.fias_street_guid,
                    self.number,
                    self.bulk
                )
                self._attach_fias_house(fias_house_guid=None, location=location)
            else:
                self._attach_fias_house(fias_house_guid)
        elif self._is_triggers(['fias_street_guid']) and not csv_condition:
            self._attach_fias_addrobj()
        fields = ['number', 'bulk', 'structure']
        if self._is_triggers(fields):
            self.short_address = construct_house_number(
                self.number,
                bulk=self.bulk,
                structure_num=self.structure,
            )
        fields = ['street', 'short_address']
        if self._is_triggers(fields):
            self.address = construct_house_address(
                self.street,
                self.short_address,
            )
        if self._is_triggers(['address']):
            self._get_geo_point()

    def _recreate_binds(self):
        from processing.models.billing.house_group import HouseGroup
        from processing.models.billing.provider.main import Provider
        from app.permissions.tasks.binds_permissions import \
            process_house_binds_models
        providers = HouseGroup.objects(houses=self.pk).distinct('provider')
        for bind in self.service_binds:
            providers.append(bind.provider)
        for provider in set(providers):
            Provider.generate_provider_binds_hg(provider)
        process_house_binds_models.delay(self.id)

    def _get_providers_including_deleted(self):
        providers = [
            x.provider
            for x in self.service_binds if x.provider
        ]
        if not self._created:
            old_house = House.objects(pk=self.pk).first()
            old_ids = [
                x.provider
                for x in old_house.service_binds if x.provider
            ]
            providers = list(set(providers) | set(old_ids))
        return providers

    def build_fias_tree(self, provider_ids: list = None) -> list:
        """
        Формирование дерева ФИАС для (управляющих организаций) дома
        """
        from app.caching.tasks.cache_update import \
            create_provider_fias_tree_cache

        if not provider_ids:
            provider_ids = self._get_providers_including_deleted()

        for _id in provider_ids:
            create_provider_fias_tree_cache.delay(provider_id=_id)

        return provider_ids

    @classmethod
    def update_gis_data(cls, house_id: ObjectId, unified_number: str):
        """Обновить идентификатор ГИС ЖКХ дома"""
        cls.objects(id=house_id).update_one(
            set__gis_uid=unified_number,
            upsert=False  # WARN не создавать новые документы
        )

    def sync_with_gis(self, do_export: bool = False):
        """Синхронизировать данные дома с ГИС ЖКХ"""
        if do_export:  # выгрузить данные дома в ГИС ЖКХ?
            from app.gis.models.gis_queued import GisQueued
            # WARN часть имеющихся данных дома теряется при выгрузке в ГИС ЖКХ
            GisQueued.put(self)  # ставим в очередь на выгрузку
        else:  # загрузить данные дома из ГИС ЖКХ!
            from app.gis.tasks.house import import_house_data
            for provider_id in self.provider_binds(True):  # управляющие
                import_house_data.delay(provider_id, self.id)  # асинхронно

    def change_setl_home_address(self):
        from app.setl_home.task.post_data import post_import_home_r2f
        provider = self.get_provider_by_business_type('udo', date_on=None)
        post_import_home_r2f.delay(
            setl_homes_address=[self.setl_home_address],
            provider=provider,
            tenants_id=False,
            mail=False,
            phone=True,
        )

    def get_developer_from_setl_home(self):
        date_on = datetime.now()
        result = False
        for bind in self.service_binds:
            # Проверим, актуальна ли привязка
            date_start = self._str_to_datetime(bind.date_start, date_on)
            date_end = self._str_to_datetime(bind.date_end, date_on)
            if (
                    bind.is_active
                    and
                    date_start <= date_on <= date_end
            ) and str(bind.provider) in SETL_GROUP_DEVELOPER:
                result = True
                break

        return result


class ChartEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    area = ObjectIdField(null=True)
    xy = ListField(IntField())
    is_united = BooleanField(default=False)
    is_manual = BooleanField(default=False)


class ShortHouseEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    address = StringField()


class Porchart(Document):
    """Квартирограмма"""

    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Porchart'
    }
    porch = ObjectIdField()
    house = ObjectIdField()
    chart = EmbeddedDocumentListField(ChartEmbedded)


class BusinessTypeEmbedded(EmbeddedDocument):
    id = ObjectIdField()
    provider = ObjectIdField()


class ActorHouseEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    address = StringField()
    business_types = EmbeddedDocumentListField(BusinessTypeEmbedded, default=[])
