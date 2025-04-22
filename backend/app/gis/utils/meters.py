from typing import Iterable

from datetime import datetime
from dateutil.relativedelta import relativedelta

from bson import ObjectId

from app.meters.models.meter import AreaMeter, HouseMeter
from app.meters.models.choices import MeterType, MeterMeasurementUnits

from app.gis.utils.common import sb

from processing.models.choices import GisDaySelection


METER_RESOURCE_NAME = {
    # region ИПУ
    MeterType.COLD_WATER_AREA_METER: 'Холодная вода',
    MeterType.HOT_WATER_AREA_METER: 'Горячая вода',
    MeterType.ELECTRIC_ONE_RATE_AREA_METER: 'Электрическая энергия',
    MeterType.ELECTRIC_TWO_RATE_AREA_METER: 'Электрическая энергия',
    MeterType.ELECTRIC_THREE_RATE_AREA_METER: 'Электрическая энергия',
    MeterType.HEAT_AREA_METER: 'Тепловая энергия',
    MeterType.HEAT_DISTRIBUTOR_AREA_METER: 'Тепловая энергия',
    MeterType.GAS_AREA_METER: 'Газ',
    # endregion ИПУ
    # region ОДПУ
    MeterType.COLD_WATER_HOUSE_METER: 'Холодная вода',
    MeterType.HOT_WATER_HOUSE_METER: 'Горячая вода',
    MeterType.ELECTRIC_ONE_RATE_HOUSE_METER: 'Электрическая энергия',
    MeterType.ELECTRIC_TWO_RATE_HOUSE_METER: 'Электрическая энергия',
    MeterType.ELECTRIC_THREE_RATE_HOUSE_METER: 'Электрическая энергия',
    MeterType.HEAT_HOUSE_METER: 'Тепловая энергия',
    MeterType.GAS_HOUSE_METER: 'Газ',
    # endregion ОДПУ
}  # используется в шаблонах

METER_RESOURCE_NSI_CODE = {
    # region ИПУ
    MeterType.COLD_WATER_AREA_METER: 1,
    MeterType.HOT_WATER_AREA_METER: 2,
    MeterType.ELECTRIC_ONE_RATE_AREA_METER: 3,
    MeterType.ELECTRIC_TWO_RATE_AREA_METER: 3,
    MeterType.ELECTRIC_THREE_RATE_AREA_METER: 3,
    MeterType.HEAT_AREA_METER: 5,
    MeterType.HEAT_DISTRIBUTOR_AREA_METER: 5,
    MeterType.GAS_AREA_METER: 4,
    # endregion ИПУ
    # region ОДПУ
    MeterType.COLD_WATER_HOUSE_METER: 1,
    MeterType.HOT_WATER_HOUSE_METER: 2,
    MeterType.ELECTRIC_ONE_RATE_HOUSE_METER: 3,
    MeterType.ELECTRIC_TWO_RATE_HOUSE_METER: 3,
    MeterType.ELECTRIC_THREE_RATE_HOUSE_METER: 3,
    MeterType.HEAT_HOUSE_METER: 5,
    MeterType.GAS_HOUSE_METER: 4
    # endregion ОДПУ
}  # 1-ХВ, 2-ГВ, 3-ЭЭ, 4-Газ, 5-ТЭ, 6-Газ в баллонах, 7-ТП, 8-СВ, 9-Не определен

METER_OKEI_UNITS = {
    '112': "Литр",
    MeterMeasurementUnits.CUBIC_METER: "Кубический метр",
    # WARN не используются: '114' - "Тыс.м3" и '214' - Киловатт
    MeterMeasurementUnits.GIGACALORIE: "Гигакалория",
    MeterMeasurementUnits.KILOWATT_PER_HOUR: "Киловатт-час",
    MeterMeasurementUnits.MEGAWATT_HOURS: "Мегаватт-час",
    '271': "Джоуль",
    MeterMeasurementUnits.GIGAJOULE: "Гигаджоуль",  # A056
    'A058': "Мегаджоуль",
}  # ЕИ для ПУ в ГИС ЖКХ


class MeteringDeviceTypeCode:  # НСИ №27
    INDIVIDUAL = '1'  # Индивидуальный ~ ИПУ
    COLLECTIVE = '2'  # Коллективный (общедомовой) ~ ОДПУ
    COMMON = '3'  # Общий (квартирный)
    ROOM = '4'  # Комнатный


def is_correct_sn(serial_number: str, min_length: int = 3) -> bool:
    """
    Проверка серийного номера ПУ на корректность

    Максимальная длина серийного номера составляет 50 знаков
    """
    if serial_number and isinstance(serial_number, str):
        if '.2015' in serial_number:  # импортные?
            return False

        if min_length <= len(serial_number.strip()) <= 50:
            return True

    return False


def get_housed_meters(meter_ids: list) -> dict:
    """Распределенные по домам идентификаторы ПУ"""
    grouped: dict = {}  # HouseId: [ MeterId,... ]

    for meter in AreaMeter.objects(__raw__={
        '_id': {'$in': meter_ids}, '_type': 'AreaMeter',  # ИПУ
    }).only('area.house').as_pymongo():
        grouped.setdefault(
            meter['area']['house']['_id'], []
        ).append(meter['_id'])

    for meter in HouseMeter.objects(__raw__={
        '_id': {'$in': meter_ids}, '_type': 'HouseMeter',  # ОДПУ
    }).only('house').as_pymongo():
        grouped.setdefault(meter['house']['_id'], []).append(meter['_id'])

    return grouped


def day_from_selection(selection) -> int:
    """
    DaySelectionType из выбранного дня ГИС ЖКХ
    """
    if selection.LastDay:  # Последний день месяца?  # Фиксированное "true"
        return GisDaySelection.NEXT_LAST \
            if selection.IsNextMonth else GisDaySelection.DAY_LAST
    elif selection.Date:  # День месяца?
        shift: int = GisDaySelection.NEXT_MONTH if selection.IsNextMonth else 0
        return shift + selection.Date  # : byte


def day_from_interval(interval) -> int:
    """
    DaySelectionType из выбранного интервала ГИС ЖКХ
    """
    if interval.LastDay:  # Фиксированное "true" - Последний день месяца?
        return GisDaySelection.NEXT_LAST \
            if interval.NextMounth else GisDaySelection.DAY_LAST \
            if interval.CurrentMounth else None  # ошибка!
    elif interval.StartDate:  # День месяца (от 1-30)?
        shift: int = GisDaySelection.NEXT_MONTH if interval.NextMounth else 0
        return shift + interval.StartDate  # : byte


def selection_name(selection: int) -> str:
    """
    Наименование выбора даты ГИС ЖКХ
    """
    if selection == GisDaySelection.NEXT_LAST:  # 199
        return "конец следующего месяца"
    elif selection == GisDaySelection.DAY_LAST:  # 99
        return "конец (текущего) месяца"
    elif selection > GisDaySelection.NEXT_MONTH:  # 100
        return f"{selection - GisDaySelection.NEXT_MONTH} следующего месяца"
    else:
        return f"{selection} текущего месяца"


def selection_from_day(day: int) -> dict:
    """
    Выбранный день ГИС ЖКХ из DaySelectionType
    """
    last_or_day = {'LastDay': True} if day in {  # Фиксированное
        GisDaySelection.DAY_LAST,
        GisDaySelection.NEXT_LAST
    } else {'Date': day}  # 1-31

    return {**last_or_day,
        'IsNextMonth': day > GisDaySelection.NEXT_MONTH}  # True или False


def interval_from_day(day: int) -> dict:
    """
    Выбранный интервал ГИС ЖКХ из DaySelectionType
    """
    last_or_day = {'LastDay': True} if day in {  # Фиксированное "true"
        GisDaySelection.DAY_LAST,
        GisDaySelection.NEXT_LAST
    } else {'StartDate': day}  # 1-30

    # WARN Mounth - ошибка в названии поля в ГИС ЖКХ
    next_or_current = {'NextMounth': True} \
        if day > GisDaySelection.NEXT_MONTH else {'CurrentMounth': True}

    return {**last_or_day, **next_or_current}


def metering_interval(day_from: int = None, day_till: int = None,
        period: datetime = None) -> tuple:
    """Даты начала и окончания приема показаний ПУ за (текущий) период"""
    if day_from is None:
        day_from = GisDaySelection.DAY_23  # по умолчанию в ГИС ЖКХ
    if day_till is None:
        day_till = GisDaySelection.DAY_LAST  # по умолчанию = DAY_31
    assert day_from < day_till, \
        "Конец срока передачи показаний ПУ пересекается с его началом"

    if not period:
        period = datetime.now()
    period = period.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    date_from: datetime = period + relativedelta(
        day=day_from % 100,
        months=day_from // 100
    )
    date_till: datetime = period + relativedelta(
        day=day_till % 100,
        months=day_till // 100
    )

    assert date_from < date_till, \
        "Окончание срока передачи показаний раньше его начала"
    delta = relativedelta(date_till, date_from)
    assert delta.years == 0 and delta.months <= 2, \
        "Период выгрузки показаний не должен превышать 2 месяца"

    return date_from, date_till


def get_resource_type(*meter_type_s: str) -> str:
    """Тип коммунального ресурса ПУ"""
    assert len(meter_type_s) > 0, \
        "Для определения ресурса необходим тип ПУ"

    for _type in meter_type_s:
        if _type in METER_RESOURCE_NAME:
            return _type

    return meter_type_s[0]  # как правило, первый элемент


def get_resource_code(meter_type, default: int = 9) -> int:
    """
    Код ГИС ЖКХ типа ресурса ПУ

    :returns:
        1 - ХВ, 2 - ГВ, 3 - ЭЭ, 4 - ГС, 5 - ТЭ, 6 - Газ в бал., 7 - ТП, 8 - СВ,
        9 - Не определен (по умолчанию)
    """
    if isinstance(meter_type, (AreaMeter, HouseMeter)):
        meter_type: dict = meter_type.to_mongo().to_dict()

    if isinstance(meter_type, dict) and '_type' in meter_type:
        meter_type: list = meter_type['_type']

    if isinstance(meter_type, (list, tuple)) and len(meter_type) > 0:
        meter_type: str = get_resource_type(*meter_type)

    assert isinstance(meter_type, str), "Некорректный тип ресурса ПУ"

    assert meter_type not in {'AreaMeter', 'HouseMeter'}, \
        "При определении кода по типу ресурса получен вид ПУ"

    assert default or meter_type in METER_RESOURCE_NSI_CODE, \
        f"Код ресурса с типом {sb(meter_type)} не определен"

    return METER_RESOURCE_NSI_CODE.get(meter_type, default)  # WARN не None


def get_house_meters(
        house_id: ObjectId,
        only_working: bool = False,
        only_closed: bool = False
) -> tuple:
    """
    Получить идентификаторы действующих ПУ (помещений) дома

    :returns: [ AreaMeterId,... ], [ HouseMeterId,... ]
    """
    # Базовые запросы
    area_meter_query: dict = {'area.house._id': house_id}
    house_meter_query: dict = {'house._id': house_id}

    # Добавление фильтров на основе флагов
    if only_working:  # Только открытые счетчики
        area_meter_query.update(AreaMeter.working_meter_query())
        house_meter_query.update(HouseMeter.working_meter_query())
    elif only_closed:  # Только закрытые счетчики
        area_meter_query.update(AreaMeter.closed_meter_query())
        house_meter_query.update(HouseMeter.closed_meter_query())

    # Возвращаем списки уникальных идентификаторов
    return (
        AreaMeter.objects(__raw__=area_meter_query).distinct('id'),
        HouseMeter.objects(__raw__=house_meter_query).distinct('id')
    )


def get_typed_meters(*meter_id_s: ObjectId) -> tuple:
    """
    Распределенные по видам (ИПУ и ОДПУ) идентификаторы ПУ

    :returns: [ AreaMeterId,... ], [ HouseMeterId,... ]
    """
    area_meters: list = AreaMeter.objects(__raw__={
        '_id': {'$in': meter_id_s}, '_type': 'AreaMeter',
    }).distinct('id')

    house_meters: list = HouseMeter.objects(__raw__={
        '_id': {'$in': meter_id_s}, '_type': 'HouseMeter',
    }).distinct('id')

    return area_meters, house_meters


def get_resource_meters(meter_ids: Iterable, meter_type: str = None) -> dict:
    """
    Распределенные по ресурсам идентификаторы ПУ

    WARN типы ресурсов ИПУ и ОДПУ различаются, а коды (ГИС ЖКХ) - совпадают

    :returns: 'resource_code': [ MeterId,... ]
    """
    resource_meters: dict = {}

    assert meter_ids, "Требуются идентификаторы распределяемых ПУ"

    for area_meter in AreaMeter.objects(__raw__={
        '_id': {'$in': meter_ids}, 'area': {'$ne': None},
        '_type': meter_type or 'AreaMeter',  # или ИПУ
    }).only('_type').as_pymongo():
        resource_code: int = get_resource_code(area_meter['_type'])
        resource_meters.setdefault(resource_code, []).append(area_meter['_id'])

    for house_meter in HouseMeter.objects(__raw__={
        '_id': {'$in': meter_ids}, 'house': {'$ne': None},
        '_type': meter_type or 'HouseMeter',  # или ОДПУ
    }).only('_type').as_pymongo():
        resource_code: int = get_resource_code(house_meter['_type'])
        resource_meters.setdefault(resource_code, []).append(house_meter['_id'])

    return resource_meters


def get_serial_number(meter_data: dict, empty: str = None) -> str:
    """Получить серийный номер ПУ"""
    assert isinstance(meter_data, dict), "Некорректный тип данных ПУ"

    return (meter_data.get('serial_number') or '').strip() or empty


def get_premisses_id(meter_data: dict) -> ObjectId:
    """Получить идентификатор места установки ПУ"""
    assert isinstance(meter_data, dict), "Некорректный тип данных ПУ"

    if meter_data.get('area'):  # AreaMeter?
        return meter_data['area']['_id']
    elif meter_data.get('house'):  # HouseMeter?
        return meter_data['house']['_id']
    else:  # нет данных (помещения) дома установки!
        raise ValueError("Отсутствуют данные о месте установки ПУ")


def get_description(meter_data: dict) -> str:
    """Получить описание места установки ПУ"""
    assert isinstance(meter_data, dict), "Некорректный тип данных ПУ"

    if meter_data.get('area'):  # AreaMeter?
        area_type = meter_data['area'].get('_type', [])  # по умолчанию = []
        number: str = meter_data['area'].get('str_number') or str(
            meter_data['area'].get('number') or meter_data['area']['_id']
        )  # int or ObjectId
        return f"{'кв.' if 'LivingArea' in area_type else 'пом.'} {number}"
    elif meter_data.get('house'):  # HouseMeter?
        return meter_data['house'].get('address') \
            or str(meter_data['house']['_id'])
    else:  # нет данных (помещения) дома установки!
        raise ValueError("Отсутствуют данные о месте установки ПУ")
