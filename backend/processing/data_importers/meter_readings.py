import datetime

from app.area.models.area import Area
from app.meters.models.meter import AreaMeter, ReadingsValidationError
from processing.models.billing.payment import WrongLineReadings
from processing.models.choices import ReadingsCreator


WATER_TYPES = ('ColdWaterAreaMeter', 'HotWaterAreaMeter')
ELECTRIC_ONE_TYPES = ('ElectricOneRateAreaMeter',)
ELECTRIC_TWO_TYPES = ('ElectricTwoRateAreaMeter',)
ELECTRIC_THREE_TYPES = ('ElectricThreeRateAreaMeter',)
HEAT_TYPES = ('HeatAreaMeter',)
HEAT_DIST_TYPES = ('HeatDistributorAreaMeter',)
GAS_TYPES = ('GasAreaMeter',)
METER_TYPES_ORDER = (
    WATER_TYPES, ELECTRIC_THREE_TYPES, ELECTRIC_TWO_TYPES, ELECTRIC_ONE_TYPES,
    HEAT_TYPES, HEAT_DIST_TYPES, GAS_TYPES
)
METER_TYPE_DESCRIPTION = {
    'ColdWaterAreaMeter': 'холодной воды',
    'HotWaterAreaMeter': 'горячей воды',
    'ElectricOneRateAreaMeter': 'электроэнергии',
    'ElectricTwoRateAreaMeter': 'электроэнергии',
    'ElectricThreeRateAreaMeter': 'электроэнергии',
    'HeatAreaMeter': 'отопления',
    'HeatDistributorAreaMeter': 'распределенного отопления',
    'GasAreaMeter': 'газа',
}


def save_readings_from_registry(area_id, registry_readings, current_period,
                                registry_number, registry_date, raw_string):
    """
    Необходимо определить в какой период вносить сданные показания (в реестре этот параметр
        не передается). Для этого проверяем есть ли документы начислений. Если их нет, то
        периодом потребления считать месяц реестра (если реестр за 29.02.2013, то период -
        февраль 2013). Если документы начисления уже есть, то необходимо определить
        максимальный период документа начислений, вычесть из него дельту из настроек
        начислений (параметр в какой месяц идут показания счетчиков - в следующий,
        текущий или предыдущий), прибавить 1 месяц. @ssv
    """
    # получим все счетчики по этой квартире, отфильтруем только по
    #  данному или меньшему периоду и оставим только последнее
    # показание, если показаний нет - отфильтровываем
    query = {
        'area._id': area_id,
        'working_start_date': {'$lte': current_period},
        '$or': [
            {'working_finish_date': {'$gt': current_period}},
            {'working_finish_date': None}
        ],
        'is_automatic': {'$ne': True},
        'is_deleted': {'$ne': True}
    }
    meters = AreaMeter.objects(__raw__=query).as_pymongo().all()
    # оставим только последнее показание
    for meter in meters:
        meter['_type'] = meter['_type'][0]
        meter['readings'] = list(
            filter(lambda x: x['period'] < current_period, meter['readings'])
        )
        if meter['readings']:
            meter['readings'] = meter['readings'][-1]
        else:
            meter['readings'] = {'values': meter['initial_values']}

    for m_types in METER_TYPES_ORDER:
        _save_readings_for(
            area_id,
            {k: v for k, v in registry_readings.items() if k in m_types},
            [m for m in meters if m['_type'] in m_types],
            current_period,
            registry_number,
            registry_date,
            raw_string,
        )


def _save_readings_for(area_id, registry_readings, meters, period,
                       registry_number, registry_date, raw_string,
                       all_names_required=True):
    """
    Сохраняет показания счетчиков из реестров для указаных типов

    :param names: перечень типов, напр. (COLD_WAM_NAME, HOT_WAM_NAME)
    :param all_names_required: если True, должны быть показания для всех типов,
        переданных в names
    """
    new_readings = []
    for meter_type, readings in registry_readings.items():
        type_meters = [m for m in meters if m['_type'] == meter_type]
        if not type_meters:
            continue
        paired = _merge_meters_to_readings(readings, type_meters)
        if paired:
            new_readings.extend(paired)
    comment = 'Реестр №{}'.format(registry_number)
    # Если найдены соответствующие счетчики для всех показаний или
    # если не обязательно наличие всех типов
    meters_to_save = []
    errors = []
    area_data = None
    meters_with_no_readings = 0
    meters_ins = []
    if len(new_readings) == len(meters) or not all_names_required:
        for readings in new_readings:
            meter = AreaMeter.objects(pk=readings[0]).get()
            meters_ins.append(meter)
            area_data = meter.area
            try:
                meter.add_readings(
                    period,
                    readings[1],
                    ReadingsCreator.REGISTRY,
                    None,
                    comment=comment,
                )
                meters_to_save.append(meter)
            except ReadingsValidationError as e:
                if any(readings[1]):
                    errors.append(
                        'Счётчик {} ({}). {}'.format(
                            METER_TYPE_DESCRIPTION[meter._type[0]],
                            meter.serial_number,
                            e.args[0],
                        ),
                    )
                else:
                    meters_with_no_readings += 1
    else:
        meters_with_no_readings = abs(len(new_readings) - len(meters))
    if meters_with_no_readings and meters_with_no_readings != len(new_readings):
        errors.append(
            'Количество показаний не соответствует количеству счётчиков',
        )
    if errors:
        if not area_data:
            area_data = Area.objects(pk=area_id).get()
        _save_bad_reading(
            area_data,
            meters_ins,
            raw_string,
            period,
            errors,
            registry_number,
            registry_date,
        )
    else:
        for meter in meters_to_save:
            meter.save(ignore_meter_validation=True)


def _merge_meters_to_readings(readings, meter_list):
    """
    Принимает список показаний из реестра и список счётчиков того же типа,
    для каждых показаний выбирает самый подходящий счётчик и возвращает список
    сопоставлений ИД счётчика и подходящие ему показаний
    """
    result = []
    # пробуем сопоставить номера счётчиков
    readings_by_sn = {r[0].upper(): r for r in readings}
    meters_by_sn = {
        m['serial_number'].replace(';', '').replace(':', '').upper(): m
        for m in meter_list
    }
    sn_is_correct = (
        len(readings_by_sn) == len(readings) and
        len(meters_by_sn) == len(meter_list)
    )
    if set(readings_by_sn).issubset(set(meters_by_sn)) and sn_is_correct:
        for sn, reading in readings_by_sn.items():
            meter = meters_by_sn[sn]
            result.append((meter['_id'], reading[2]))
    else:
        # по номерам не удалось, ищем ближайшие по значению
        for reading in sorted(readings, key=lambda x: x[2][0], reverse=True):
            meter_list = list(sorted(
                meter_list,
                key=lambda x: x['readings']['values'][0],
                reverse=True
            ))
            if meter_list:
                meter = meter_list.pop(0)
                result.append((meter['_id'], reading[2]))
    return result


def _save_bad_reading(area, meters, raw_string, period, errors,
                      registry_number, registry_date):
    """
    Добавим плохие строки показаний
    """
    last_reading_meters = []
    try:
        for meter in meters:
            if len(meter.readings):
                last_reading = meter.readings[-1].values
            else:
                last_reading = meter.initial_values
            for value in last_reading:
                last_reading_meters.append(dict(
                    type=meter._type[0],
                    _id=None,
                    reading=value,
                    number=meter.serial_number,
                ))
    except Exception:
        pass
    WrongLineReadings(
        area={
            '_id': area.id if hasattr(area, 'id') else area.pk,
            '_type': area._type,
            'number': area.number,
            'house': {
                '_id': area.house.id,
                'address': area.house.address,
            },
        },
        _type=['WrongLineReadings', 'WrongLine'],
        wrong_line=raw_string,
        registry_number=registry_number,
        date_reg=registry_date,
        date_doc=registry_date,
        date=datetime.datetime.now(),
        month=period,
        meters=last_reading_meters,
        errors=errors
    ).save()

