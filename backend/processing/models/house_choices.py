
class CommunitySystem:
    STAIR_LANDINGS = 'stair_landings'
    STAIRS = 'stairs'
    LIFTS = 'lifts'
    MINES = 'mines'
    CORRIDORS = 'corridors'
    PRAMS = 'prams'
    TECH_FLOORS = 'tech_floors'
    TECH_LOFTS = 'tech_lofts'
    TECH_CELLARS = 'tech_cellars'
    LOFTS = 'lofts'
    GARAGES = 'garages'
    AREAS_AUTO = 'areas_auto'
    WORKSHOPS = 'workshops'
    BOILERS = 'boilers'
    ELEVATOR = 'elevator'
    ROOFS = 'roofs'
    FOUNDATIONS = 'foundations'
    WALLS = 'walls'
    SLABS = 'slabs'
    PLATES = 'plates'
    COLUMNS = 'columns'
    BEARING_OTHER = 'bearing_other'
    WINDOORS = 'windoors'
    RAILING = 'railing'
    PARAPETS = 'parapets'
    PROTECTING_OTHER = 'protecting_other'
    MECHANICAL = 'mechanical'
    ELECTRICAL = 'electrical'
    SANITARY = 'sanitary'
    EQUIPMENT_OTHER = 'equipment_other'
    GROUND = 'ground'
    TRANSFORMERS = 'transformers'
    HEATINGS = 'heatings'
    PARKINGS = 'parkings'
    PLAYGROUNDS = 'playgrounds'
    SYSTEM_WATER = 'system_water'
    SYSTEM_DRAINAGE = 'system_drainage'
    SYSTEM_GAS = 'system_gas'
    SYSTEM_HEATING = 'system_heating'
    SYSTEM_POWER = 'system_power'


# Помещения в многоквартирном доме
COMMUNITY_AREAS_CHOICES = (
    (CommunitySystem.STAIR_LANDINGS, 'межквартирные лестничные площадки'),
    (CommunitySystem.STAIRS, 'лестницы'),
    (CommunitySystem.LIFTS, 'лифты'),
    (CommunitySystem.MINES, 'лифтовые и иные шахты'),
    (CommunitySystem.CORRIDORS, 'коридоры'),
    (CommunitySystem.PRAMS, 'колясочные'),
    (CommunitySystem.TECH_FLOORS, 'технические этажи'),
    (CommunitySystem.TECH_LOFTS, 'технические чердаки'),
    (CommunitySystem.TECH_CELLARS, 'технические подвалы'),
    (CommunitySystem.LOFTS, 'чердаки'),
    (CommunitySystem.GARAGES, 'встроенные гаражи'),
    (CommunitySystem.AREAS_AUTO, 'площадки для автомобильного транспорта'),
    (CommunitySystem.WORKSHOPS, 'мастерские'),
    (CommunitySystem.BOILERS, 'котельные'),
    (CommunitySystem.ELEVATOR, 'элеваторные узлы'),
)
# Крыши
COMMUNITY_ROOFS_CHOICES = (
    (CommunitySystem.ROOFS, 'крыши'),
)
# Ограждающие несущие конструкции многоквартирного дома
COMMUNITY_BEARING_CHOICES = (
    (CommunitySystem.FOUNDATIONS, 'фундаменты'),
    (CommunitySystem.WALLS, 'несущие стены'),
    (CommunitySystem.SLABS, 'плиты перекрытий'),
    (CommunitySystem.PLATES, 'балконные и иные плиты'),
    (CommunitySystem.COLUMNS, 'несущие колонны'),
    (CommunitySystem.BEARING_OTHER, 'иные несущие конструкции'),
)
# Ограждающие ненесущие конструкции многоквартирного дома
COMMUNITY_PROTECTING_CHOICES = (
    (CommunitySystem.WINDOORS, 'окна и двери помещений общего пользования'),
    (CommunitySystem.RAILING, 'перила'),
    (CommunitySystem.PARAPETS, 'парапеты'),
    (CommunitySystem.PROTECTING_OTHER, 'иные ограждающие ненесущие конструкции')
)
# Механическое, электрическое, санитарно-техническое и иное оборудование
COMMUNITY_EQUIPMENT_CHOICES = (
    (CommunitySystem.MECHANICAL, 'механическое'),
    (CommunitySystem.ELECTRICAL, 'электрическое'),
    (CommunitySystem.SANITARY, 'санитарно-техническое'),
    (CommunitySystem.EQUIPMENT_OTHER, 'иное оборудование'),
)
# Земельный участок, на котором расположен многоквартирный дом
COMMUNITY_GROUND_CHOICES = (
    (CommunitySystem.GROUND, 'земельный участок'),
)
# Иные объекты, предназначенные для обслуживания,
# эксплуатации и благоустройства многоквартирного дома
COMMUNITY_MAINTENANCE_CHOICES = (
    (CommunitySystem.TRANSFORMERS, 'трансформаторные подстанции'),
    (CommunitySystem.HEATINGS, 'тепловые пункты'),
    (CommunitySystem.PARKINGS, 'коллективные автостоянки'),
    (CommunitySystem.GARAGES, 'гаражи'),
    (CommunitySystem.PLAYGROUNDS, 'детские и спортивные площадки'),
)
# Внутридомовые инженерные системы холодного и горячего водоснабжения
COMMUNITY_SYSTEM_WATER_CHOICES = (
    (
        CommunitySystem.SYSTEM_WATER,
        'инженерные системы холодного и горячего водоснабжения',
    ),
)
# Внутридомовая инженерная система водоотведения
COMMUNITY_SYSTEM_DRAINAGE_CHOICES = (
    (CommunitySystem.SYSTEM_DRAINAGE, 'инженерная система водоотведения'),
)
# Внутридомовая инженерная система газоснабжения
COMMUNITY_SYSTEM_GAS_CHOICES = (
    (CommunitySystem.SYSTEM_GAS, 'инженерная система газоснабжения'),
)
# Внутридомовая система отопления
COMMUNITY_SYSTEM_HEATING_CHOICES = (
    (CommunitySystem.SYSTEM_HEATING, 'система отопления'),
)
# Внутридомовая система электроснабжения
COMMUNITY_SYSTEM_POWER_CHOICES = (
    ('system_power', 'система электроснабжения'),
)
ALL_COMMUNITY_SYSTEMS_CHOICES = (
    COMMUNITY_AREAS_CHOICES,
    COMMUNITY_ROOFS_CHOICES,
    COMMUNITY_BEARING_CHOICES,
    COMMUNITY_PROTECTING_CHOICES,
    COMMUNITY_EQUIPMENT_CHOICES,
    COMMUNITY_GROUND_CHOICES,
    COMMUNITY_MAINTENANCE_CHOICES,
    COMMUNITY_SYSTEM_WATER_CHOICES,
    COMMUNITY_SYSTEM_DRAINAGE_CHOICES,
    COMMUNITY_SYSTEM_GAS_CHOICES,
    COMMUNITY_SYSTEM_HEATING_CHOICES,
    COMMUNITY_SYSTEM_POWER_CHOICES,
)
# Создаем единый choices
ALL_COMMUNITY_SYSTEMS_CHOICES = tuple(
    [y[0] for x in ALL_COMMUNITY_SYSTEMS_CHOICES for y in x]
)


class BuildingDesignType:
    PANEL = 'panel'
    BLOCK = 'block'
    BRICK = 'brick'
    TIMBER = 'timber'


# Тип проекта здания
BUILDING_DESIGN_TYPES_CHOICES = (
    (BuildingDesignType.PANEL, 'панельный'),
    (BuildingDesignType.BLOCK, 'блочный'),
    (BuildingDesignType.BRICK, 'кирпичный'),
    (BuildingDesignType.TIMBER, 'деревянный'),
)


class WellType:
    EXT = 'ext'
    INT = 'int'


WELL_TYPES_CHOICES = (
    (WellType.EXT, 'приставная'),
    (WellType.INT, 'встроенная'),
)


class ResourceType:
    HOT_WATER = 'ХВС'
    COLD_WATER = 'SХВ'
    GAS = 'SГЗ'
    HEAT = 'SОТ'
    ELECTRICITY = 'SЭЛ'


RESOURCE_TYPES_CHOICES = (
    (ResourceType.HOT_WATER, 'горячая вода'),
    (ResourceType.COLD_WATER, 'холодная вода'),
    (ResourceType.GAS, 'поставка газа'),
    (ResourceType.HEAT, 'тепловая энергия'),
    (ResourceType.ELECTRICITY, 'электрическая энергия'),
)


class HeatingType:
    CENTRAL = 'central'
    AUTO = 'auto'
    APARTMENT = 'aprt'
    OVEN = 'oven'
    NONE = 'none'


HEATING_TYPES_CHOICES = (
    (HeatingType.CENTRAL, 'центральное'),
    (HeatingType.AUTO, 'автономная котельная'),
    (HeatingType.APARTMENT, 'квартирное отопление'),
    (HeatingType.OVEN, 'печное отопление'),
    (HeatingType.NONE, 'отсутствует'),
)


class HotWaterSupplyType:
    INDIVIDUAL = 'individ'
    CENTRAL = 'central'
    AUTO = 'auto'
    APARTMENT = 'aprt'
    WOOD = 'wood'
    NONE = 'none'


HOT_WATER_SUPPLY_TYPES_CHOICES = (
    (HotWaterSupplyType.INDIVIDUAL, 'индивидуальный водонагреватель'),
    (HotWaterSupplyType.CENTRAL, 'центральное'),
    (HotWaterSupplyType.AUTO, 'автономная котельная'),
    (HotWaterSupplyType.APARTMENT, 'квартирное отопление'),
    (HotWaterSupplyType.WOOD, 'от дровяных колонок'),
    (HotWaterSupplyType.NONE, 'отсутствует'),
)


class ColdWaterSupplyType:
    CENTRAL = 'central'
    NONE = 'none'


COLD_WATER_SUPPLY_TYPES_CHOICES = (
    (ColdWaterSupplyType.CENTRAL, 'центральное'),
    (ColdWaterSupplyType.NONE, 'отсутствует'),
)


class SewerageType:
    CENTRAL = 'central'
    NONE = 'none'


SEWERAGE_TYPES_CHOICES = (
    (SewerageType.CENTRAL, 'центральное'),
    (SewerageType.NONE, 'отсутствует'),
)


class PowerSupplyType:
    CENTRAL = 'central'
    NONE = 'none'


POWER_SUPPLY_TYPES_CHOICES = (
    (PowerSupplyType.CENTRAL, 'центральное'),
    (PowerSupplyType.NONE, 'отсутствует'),
)


class GasSupplyType:
    NON_CENTRAL = 'non_central'
    CENTRAL = 'central'
    NONE = 'none'


GAS_SUPPLY_TYPES_CHOICES = (
    (GasSupplyType.NON_CENTRAL, 'нецентральное'),
    (GasSupplyType.CENTRAL, 'центральное'),
    (GasSupplyType.NONE, 'отсутствует'),
)


class VentilationType:
    FORCED = 'forced'
    EXHAUST = 'exhaust'
    PURGE = 'purge'
    NONE = 'none'


VENTILATION_TYPES_CHOICES = (
    (VentilationType.FORCED, 'приточная вентиляция'),
    (VentilationType.EXHAUST, 'вытяжная вентиляция'),
    (VentilationType.PURGE, 'приточно-вытяжная вентиляция'),
    (VentilationType.NONE, 'отсутствует'),
)


class StormSewageType:
    EXTERNAL = 'external'
    INTERNAL = 'iternal'
    NONE = 'none'


STORM_SEWAGE_TYPES_CHOICES = (
    (StormSewageType.EXTERNAL, 'наружные водостоки'),
    (StormSewageType.INTERNAL, 'внутренние водостоки'),
    (StormSewageType.NONE, 'отсутствует'),
)


# Распопложение приемо-загрузочных клапанов
class BootReceiveValvePlacement:
    APARTMENT = 'aprt'
    STAIRS = 'stairs'
    SPECIAL = 'special'


BOOT_RECEIVE_VALVE_PLACEMENTS_CHOICES = (
    (
        BootReceiveValvePlacement.APARTMENT,
        'квартирные',
    ),
    (
        BootReceiveValvePlacement.STAIRS,
        'лестничная клетка',
    ),
    (
        BootReceiveValvePlacement.SPECIAL,
        'обособленные помещения на лестничной  клетке',
    ),
)


class EnergyEfficiencyClass:
    A = 'a'  # менее -45
    BPP = 'b++'  # от -36 до -45 включительно
    BP = 'b+'  # от -26 до -35 включительно
    B = 'b'  # от -11 до -25 включительно
    C = 'c'  # от +5 до -10 включительно
    D = 'd'  # от +6 до +50 включительно
    E = 'e'  # более +51


ENERGY_EFFICIENCY_CLASS_CHOICES = (
    (EnergyEfficiencyClass.A, 'наивысший'),
    (EnergyEfficiencyClass.BPP, 'повышенный ++'),
    (EnergyEfficiencyClass.BP, 'повышенный +'),
    (EnergyEfficiencyClass.B, 'высокий'),
    (EnergyEfficiencyClass.C, 'нормальный'),
    (EnergyEfficiencyClass.D, 'пониженный'),
    (EnergyEfficiencyClass.E, 'низший'),
)


class AreaLocation:
    WC = 'wc'
    HALL = 'hall'
    GARAGE = 'garage'
    TOILET = 'toilet'
    STOREY = 'storey'
    LIVING = 'living'
    KITCHEN = 'kitchen'
    CORRIDOR = 'corridor'
    BATHROOM = 'bathroom'


AREA_LOCATIONS_CHOICES = (
    (AreaLocation.WC, 'санузел'),
    (AreaLocation.HALL, 'прихожая'),
    (AreaLocation.GARAGE, 'гараж'),
    (AreaLocation.TOILET, 'туалет'),
    (AreaLocation.STOREY, 'этажная площадка'),
    (AreaLocation.LIVING, 'жилая комната'),
    (AreaLocation.KITCHEN, 'кухня'),
    (AreaLocation.CORRIDOR, 'коридор'),
    (AreaLocation.BATHROOM, 'ванная'),
)


class WaterSupplyZone:
    LOWER = 'lower'
    UPPER = 'upper'


WATER_SUPPLY_ZONES_CHOICES = (
    ('lower', 'нижняя'),
    ('upper', 'верхняя'),
)


class WaterType(object):
    HOT = 'hot'
    COLD = 'cold'
    CENTRAL = 'central'
    GAZ = 'gaz'


WATER_TYPE_CHOICES = (
    (WaterType.HOT, 'ГВС'),
    (WaterType.COLD, 'ХВС'),
    (WaterType.CENTRAL, 'ЦО'),
    (WaterType.GAZ, 'Газ'),
)

class HousePorchIntercomType(object):
    NONE = 'none'
    MECHANIC = 'mechanic'
    ELECTRIC = 'electric'


HOUSE_PORCH_INTERCOM_CHOICES = (
    (HousePorchIntercomType.NONE, 'нет'),
    (HousePorchIntercomType.MECHANIC, 'механический'),
    (HousePorchIntercomType.ELECTRIC, 'электронный'),
)


class ProtocolCategory:
    CAPITAL_REPAIR_TARIFF = 'capital_repair_tariff'
    CAPITAL_REPAIR_TYPE = 'capital_repair_type'


PROTOCOL_CATEGORIES_CHOICES = (
    (
        ProtocolCategory.CAPITAL_REPAIR_TARIFF,
        'Решение о тарифе на капитальный ремонт',
    ),
    (
        ProtocolCategory.CAPITAL_REPAIR_TYPE,
        'Решение о выборе способа формирования фонда капитального ремонта',
    ),
)


class ProtocolResult:
    NONE = 'none'
    CAPITAL_REPAIR_OWN_ACCOUNT = 'capital_repair_own_account'
    CAPITAL_REPAIR_REGIONAL_OPERATOR = 'capital_repair_regional_operator'


PROTOCOL_RESULTS_CHOICES = (
    (
        ProtocolResult.NONE,
        '',
    ),
    (
        ProtocolResult.CAPITAL_REPAIR_OWN_ACCOUNT,
        'Специальный счёт',
    ),
    (
        ProtocolResult.CAPITAL_REPAIR_REGIONAL_OPERATOR,
        'Счёт регионального оператора',
    ),
)


class HouseEngineeringStatusTypes:
    EMERGENCY = 'emergency'
    GOOD = 'good'
    OLD = 'old'
    UNKNOWN = 'unknown'


HOUSE_ENGINEERING_STATUS_CHOICES = (
    (HouseEngineeringStatusTypes.EMERGENCY, 'Аварийный'),
    (HouseEngineeringStatusTypes.GOOD, 'Исправный'),
    (HouseEngineeringStatusTypes.OLD, 'Ветхий'),
)
HOUSE_ENGINEERING_STATUS_NSI_CODE_CHOICES = (
    (HouseEngineeringStatusTypes.EMERGENCY, 1),
    (HouseEngineeringStatusTypes.GOOD, 2),
    (HouseEngineeringStatusTypes.OLD, 3),
    (HouseEngineeringStatusTypes.UNKNOWN, 4),
)


class HouseCategory:
    GERMAN = 'de'
    KHRUSCHEVS = 'khr'
    STALINS = 'stl'
    CONSTRUCTIVISM = 'cnstr'
    NEWLY = 'newly'


HOUSE_CATEGORIES_CHOICES = (
    (HouseCategory.GERMAN, 'Немецкие'),
    (HouseCategory.KHRUSCHEVS, 'Хрущевки'),
    (HouseCategory.STALINS, 'Сталинские'),
    (HouseCategory.CONSTRUCTIVISM, 'Конструктивизм'),
    (HouseCategory.NEWLY, 'Новое строительство'),
)


class HouseType:
    NOT_SET = 'not_set'
    MODULAR = 'modular'
    WOODEN = 'wooden'
    MONOLITH_BRICK = 'monolith_brick'
    BRICK = 'brick'
    LARGE_PANEL = 'large_panel'
    MONOLITH = 'monolith'
    PANEL = 'panel'


HOUSE_TYPES_CHOICES = (
    (HouseType.NOT_SET, 'не указан'),
    (HouseType.MODULAR, 'Блочный'),
    (HouseType.WOODEN, 'Деревянный'),
    (HouseType.MONOLITH_BRICK, 'Кирпично-монолитный'),
    (HouseType.BRICK, 'Кирпичный'),
    (HouseType.LARGE_PANEL, 'Крупно-панельный'),
    (HouseType.MONOLITH, 'Монолитный'),
    (HouseType.PANEL, 'Панельный'),
)
HOUSE_TYPES_CHOICES_AS_DICT = {v[0]: v[1] for v in HOUSE_TYPES_CHOICES}


class StructureElement:
    FOUNDATIONS = 'foundations'
    WALLS = 'walls'
    COLUMNS = 'columns'
    BEAMS = 'beams'
    ROOFS = 'roofs'
    STAIRS = 'stairs'
    FACADES = 'facades'
    SEPTA = 'septa'
    TRIMS = 'trims'
    FLOORS = 'floors'
    FILLINGS = 'fillings'
    CHUTES = 'chutes'
    STOVES = 'stoves'


STRUCTURE_ELEMENTS_CHOICES = (
    (StructureElement.FOUNDATIONS, 'фундаменты'),
    (StructureElement.WALLS, 'стены'),
    (StructureElement.COLUMNS, 'колонны и столбы'),
    (StructureElement.BEAMS, 'балки (ригели) перекрытий и покрытий'),
    (StructureElement.ROOFS, 'крыши'),
    (StructureElement.STAIRS, 'лестницы'),
    (StructureElement.FACADES, 'фасады'),
    (StructureElement.SEPTA, 'перегородки'),
    (StructureElement.TRIMS, 'внутренняя отделка'),
    (StructureElement.FLOORS, 'полы помещений'),
    (StructureElement.FILLINGS, 'оконные и дверные заполнения помещений'),
    (StructureElement.CHUTES, 'мусоропроводы'),
    (StructureElement.STOVES, 'печи, камины и очаги'),
)


class EquipmentElement:
    CWS = 'cws'
    KWS = 'kws'
    LIFTS = 'lifts'
    POWER = 'power'
    DRAINAGE = 'drainage'
    INDIVIDUAL = 'individual'
    GAS_SYSTEMS = 'gas_system'
    ELECTRICAL = 'electrical'
    VENTILATION = 'ventilation'
    HEATING_SYSTEM = 'heating_system'


EQUIPMENT_ELEMENTS_CHOICES = (
    (EquipmentElement.CWS, 'система холодного водоснабжения'),
    (EquipmentElement.KWS, 'система горячего водоснабжения'),
    (EquipmentElement.LIFTS, 'лифты'),
    (EquipmentElement.POWER, 'система электроснабжения'),
    (EquipmentElement.DRAINAGE, 'система водоотведения'),
    (
        EquipmentElement.INDIVIDUAL,
        'индивидуальные тепловые пункты и водоподкачки',
    ),
    (
        EquipmentElement.GAS_SYSTEMS,
        'системы внутридомового газового оборудования',
    ),
    (
        EquipmentElement.ELECTRICAL,
        'электрооборудование, радио- и телекоммуникационное оборудование',
    ),
    (EquipmentElement.VENTILATION, 'системы вентиляции и дымоудаления'),
    (EquipmentElement.HEATING_SYSTEM, 'система теплоснабжения'),
)


class PrintBillsType:
    ENTIRE = 'entire'
    NO_CHANNELS = 'no_channels'
    ONLY_PAPERS = 'only_papers'


PRINT_BILLS_TYPE_CHOICES = (
    # Печатать ли квитанции жителям
    (PrintBillsType.ENTIRE, 'Печатать всем жителям'),
    (PrintBillsType.NO_CHANNELS, 'Тем, у кого отсутствуют каналы связи'),
    (PrintBillsType.ONLY_PAPERS, 'Тем, кто не отказался от бумаги'),
)
