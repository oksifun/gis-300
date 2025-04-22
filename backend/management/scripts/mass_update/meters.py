from bson import ObjectId

import datetime

from app.house.models.house import House
from app.meters.models.meter import (
    AreaMeter,
    HouseMeter,
    MeterDataValidationError,
)

from lib.helpfull_tools import DateHelpFulls
from lib.type_convert import str_to_bool

from processing.data_producers.associated.base import get_binded_houses
from processing.models.logging.custom_scripts import CustomScriptData

from dateutil.relativedelta import relativedelta


def close_electric_meters(logger, task, house_id, date,
                          try_close_next_month=False,
                          allow_remove_readings=False):
    """
    Массово закрывает учёт счётчиков электричества

    :param logger: функция, которая пишет логи
    :param task: задача, запустившая скрипт
    :param house_id: дом
    :param date: дата окончания учёта
    :param try_close_next_month: делать ли попытку закрыть следующим месяцем
    :param allow_remove_readings: удалять последующие показания
    """
    house_id = ObjectId(house_id)
    if isinstance(try_close_next_month, str):
        try_close_next_month = str_to_bool(try_close_next_month)
    if isinstance(allow_remove_readings, str):
        allow_remove_readings = str_to_bool(allow_remove_readings)
    if isinstance(date, str):
        date = datetime.datetime.strptime(date, '%d.%m.%Y')
    mm = AreaMeter.objects(__raw__={
        '_type': {'$in': [
            'ElectricThreeRateAreaMeter',
            'ElectricTwoRateAreaMeter',
            'ElectricOneRateAreaMeter',
        ]},
        'area.house._id': house_id,
        'working_finish_date': None,
    })
    CustomScriptData(
        task=task.id if task else None,
        coll='Meter',
        data=list(mm.as_pymongo())
    ).save()
    logger('найдено {}'.format(mm.count()))
    errors = []
    for m in mm._iter_results():
        try:
            if allow_remove_readings:
                for r in m.readings:
                    if r.period > date:
                        m.readings = [
                            rr for rr in m.readings if rr.period <= date
                        ]
                        m.save()
                        break
            m.working_finish_date = date
            m.save()
        except Exception:
            errors.append(m)
            logger('ошибка месяца в пом. {}'.format(m.area.str_number))
    if errors and try_close_next_month:
        logger('всего ошибок: {} ставлю следующий месяц'.format(len(errors)))
        date_n = date + relativedelta(months=1)
        date_n = datetime.datetime(date_n.year, date_n.month, 1)
        for m in errors:
            try:
                m.working_finish_date = date_n
                m.save()
            except Exception:
                logger('всё равно ошибка в пом. {}'.format(m.area.str_number))


def close_heat_meters(logger, task, house_id, date, try_close_next_month=False,
                      allow_remove_readings=False):
    """
    Массово закрывает учёт счётчиков тепла

    :param logger: функция, которая пишет логи
    :param task: задача, запустившая скрипт
    :param house_id: дом
    :param date: дата окончания учёта
    :param try_close_next_month: делать ли попытку закрыть следующим месяцем
    :param allow_remove_readings: удалять последующие показания
    """
    house_id = ObjectId(house_id)
    if isinstance(try_close_next_month, str):
        try_close_next_month = str_to_bool(try_close_next_month)
    if isinstance(allow_remove_readings, str):
        allow_remove_readings = str_to_bool(allow_remove_readings)
    if isinstance(date, str):
        date = datetime.datetime.strptime(date, '%d.%m.%Y')
    mm = AreaMeter.objects(__raw__={
        '_type': 'HeatAreaMeter',
        'area.house._id': house_id,
        'working_finish_date': None,
    })
    CustomScriptData(
        task=task.id if task else None,
        coll='Meter',
        data=list(mm.as_pymongo())
    ).save()
    logger('найдено {}'.format(mm.count()))
    errors = []
    for m in mm._iter_results():
        try:
            if allow_remove_readings:
                for r in m.readings:
                    if r.period > date:
                        m.readings = [
                            rr for rr in m.readings if rr.period <= date
                        ]
                        m.save()
                        break
            m.working_finish_date = date
            m.save()
        except Exception:
            errors.append(m)
            logger('ошибка месяца в пом. {}'.format(m.area.str_number))
    if errors and try_close_next_month:
        logger('всего ошибок: {} ставлю следующий месяц'.format(len(errors)))
        date_n = date + relativedelta(months=1)
        date_n = datetime.datetime(date_n.year, date_n.month, 1)
        for m in errors:
            try:
                m.working_finish_date = date_n
                m.save()
            except Exception:
                logger('всё равно ошибка в пом. {}'.format(m.area.str_number))


def close_meters(logger, task, house_id, meter_type, date,
                 try_close_next_month=False, allow_remove_readings=False):
    """
    Массово закрывает учёт счётчиков указанного типа

    :param logger: функция, которая пишет логи
    :param task: задача, запустившая скрипт
    :param house_id: дом
    :param meter_type: тип счётчиков
    :param date: дата окончания учёта
    :param try_close_next_month: делать ли попытку закрыть следующим месяцем
    :param allow_remove_readings: удалять последующие показания
    """
    house_id = ObjectId(house_id)
    if isinstance(try_close_next_month, str):
        try_close_next_month = str_to_bool(try_close_next_month)
    if isinstance(allow_remove_readings, str):
        allow_remove_readings = str_to_bool(allow_remove_readings)
    if isinstance(date, str):
        date = datetime.datetime.strptime(date, '%d.%m.%Y')
    mm = AreaMeter.objects(__raw__={
        '_type': meter_type,
        'area.house._id': house_id,
        'working_finish_date': None,
    })
    num = 0
    while num < len(mm):
        # Значение оффсета изменено на меньшее из-за лимита BSON на 16 mb
        CustomScriptData(
            task=task.id if task else None,
            coll='Meter',
            data=list(mm.as_pymongo()[num:num+100])
        ).save()
        num += 100
    logger('найдено {}'.format(mm.count()))
    errors = []
    for m in mm._iter_results():
        try:
            if allow_remove_readings:
                for r in m.readings:
                    if r.period > date:
                        m.readings = [
                            rr for rr in m.readings if rr.period <= date
                        ]
                        m.save()
                        break
            m.working_finish_date = date
            m.save()
        except Exception:
            errors.append(m)
            logger('ошибка месяца в пом. {}'.format(m.area.str_number))
    if errors and try_close_next_month:
        logger('всего ошибок: {} ставлю следующий месяц'.format(len(errors)))
        date_n = date + relativedelta(months=1)
        date_n = datetime.datetime(date_n.year, date_n.month, 1)
        for m in errors:
            try:
                m.working_finish_date = date_n
                m.save()
            except Exception:
                logger('всё равно ошибка в пом. {}'.format(m.area.str_number))


def set_meters_automatic(logger, task, house_id,
                         meter_type=None, set_true=True):
    """
    Проставляет квартирным счётчикам в доме параметр "автоматизированный"
    :param logger: функция, которая пишет логи
    :param task: задача, запустившая скрипт
    :param house_id: дом
    :param meter_type: тип счётчика - необязательный
    :param set_true: поставить галочку - по умолчанию да
    """
    value = str_to_bool(set_true)
    q = {'area.house._id': ObjectId(house_id), 'is_automatic': {'$ne': value}}
    if meter_type:
        q['_type'] = meter_type
    mm = AreaMeter.objects(__raw__=q)
    logger('найдено {}'.format(mm.count()))
    CustomScriptData(
        task=task.id if task else None,
        coll='Meter',
        data=list(mm.only('id', 'is_automatic').as_pymongo())
    ).save()
    r = mm.update(set__is_automatic=value)
    logger(meter_type, str(r))


def set_meters_automatic_by_provider(logger, task, provider_id,
                                     meter_type=None):
    """
    Проставляет квартирным счётчикам в домов организации параметр
    "автоматизированный"
    :param logger: функция, которая пишет логи
    :param provider_id: организация
    :param meter_type: тип счётчика - необязательный
    """
    hh = get_binded_houses(ObjectId(provider_id))
    logger('домов {}'.format(len(hh)))
    for h in hh:
        set_meters_automatic(logger, task, h, meter_type=meter_type)


def drop_meters(logger, task, house_id, meter_type=None):
    """
    Удаляет квартирные счётчикам в доме навсегда
    :param logger: функция, которая пишет логи
    :param task: задача, запустившая скрипт
    :param house_id: дом
    :param meter_type: тип счётчика - необязательный
    """
    q = {'area.house._id': ObjectId(house_id)}
    if meter_type:
        q['_type'] = meter_type
    mm = AreaMeter.objects(__raw__=q)
    logger('найдено {}'.format(mm.count()))
    CustomScriptData(
        task=task.id if task else None,
        coll='Meter',
        data=list(mm.as_pymongo())
    ).save()
    r = mm.delete()
    logger(meter_type, str(r))


def move_meters_readings_periods(logger, task, house_id, date_till=None,
                                 down=True, months=1, only_readings=False,
                                 area_meters=True, house_meters=True):
    """
    Меняет периоды показаний счётчиков - уменьшает или увеличивает на указанное
    количество месяцев
    :param logger: функция, которая пишет логи
    :param task: задача, запустившая скрипт
    :param house_id: дом
    :param date_till: по какой месяц
    :param down: уменьшать или увеличивать
    :param months: на какое количество месяцев менять
    :param only_readings: менять только показания, а начало учёта не трогать
    :param area_meters: только квартирные счётчики
    """
    house_id = ObjectId(house_id)
    months = int(months)
    if isinstance(down, str):
        down = str_to_bool(down)
    if isinstance(only_readings, str):
        only_readings = str_to_bool(only_readings)
    if isinstance(area_meters, str):
        area_meters = str_to_bool(area_meters)
    if isinstance(house_meters, str):
        house_meters = str_to_bool(house_meters)
    if isinstance(date_till, str):
        date_till = datetime.datetime.strptime(date_till, '%d.%m.%Y')

    def delta(dt):
        if down:
            return dt - relativedelta(months=months)
        else:
            return dt + relativedelta(months=months)

    def set_readings(meter):
        for readings in meter.readings:
            if not date_till or readings.period <= date_till:
                readings.period = delta(readings.period)
        meter.safely_readings_added = True

    def set_working_start_dates(meter):
        meter.installation_date = delta(meter.installation_date)
        ws_date = delta(meter.working_start_date)
        if len(meter.readings) > 0:
            ws_month = DateHelpFulls.begin_of_month(ws_date)
            if ws_month > meter.readings[0].period:
                if hasattr(meter, 'area'):
                    logger('ошибка периода {} {}'.format(
                        meter.area.house.address,
                        meter.area.str_number
                    ))
                else:
                    logger('ошибка периода {}'.format(meter.house.address))
                ws_date = meter.readings[0].period
        meter.working_start_date = ws_date
        if meter.last_check_date:
            meter.last_check_date = delta(meter.last_check_date)

    def set_working_finish_dates(meter):
        if meter.working_finish_date:
            wf_date = delta(meter.working_finish_date)
            if len(meter.readings) > 0:
                wf_month = DateHelpFulls.begin_of_month(wf_date)
                if wf_month > meter.readings[-1].period:
                    if hasattr(meter, 'area'):
                        logger('ошибка периода {} {}'.format(
                            meter.area.house.address,
                            meter.area.str_number
                        ))
                    else:
                        logger('ошибка периода {}'.format(meter.house.address))
                    wf_date = meter.readings[-1].period
            meter.working_finish_date = wf_date

    def update_meters(meters_query_set):
        """Изменено поведение скрипта, теперь если period будет установлен на более позднюю дату,
        чем working_finish_date, working_finish_date будет также увеличен на месяц.
         Если после возникнет ошибка валидации, скрипт продолжит работу, пропустив объект с невалидными данными """
        for meter in meters_query_set._iter_results():
            if only_readings:
                try:
                    set_readings(meter)
                    meter.save()
                except MeterDataValidationError:
                    try:
                        set_working_finish_dates(meter)
                        meter.save()
                    except MeterDataValidationError:
                        continue
            elif down:
                set_working_start_dates(meter)
                set_readings(meter)
                set_working_finish_dates(meter)
                meter.save(ignore_meter_validation=True)
            else:
                set_working_finish_dates(meter)
                set_readings(meter)
                set_working_start_dates(meter)
                meter.save(ignore_meter_validation=True)

    if area_meters:
        # квартирные
        num = 500
        query = {'area.house._id': house_id, 'is_deleted': {'$ne': True}}
        meters_all = AreaMeter.objects(__raw__=query)
        count = meters_all.count()
        logger('нашла квартирных {}'.format(count))
        for i in range(0, count, num):
            meters = meters_all[i:i + num]
            total = len(meters)
            CustomScriptData(
                task=task.id if task else None,
                coll='Meter',
                data=list(meters.as_pymongo())
            ).save()
            update_meters(meters)
            logger(f'обновила квартирных {total}')
    if house_meters:
        # домовые
        meters = HouseMeter.objects(__raw__={'house._id': house_id})
        total = meters.count()
        logger('нашла домовых {}'.format(total))
        CustomScriptData(
            task=task.id if task else None,
            coll='Meter',
            data=list(meters.as_pymongo())
        ).save()
        update_meters(meters)
        logger('обновила')


def delete_broken_readings(logger, task, house_id):
    """
    Удаляет некорректные показания по дому в квартирных счетчиках
    (проверяется наличем поля - period).

    Args:
        logger: Функция логирования
        task: Celery задача
        house_id: ID дома, для которого нужно удалить неверные показания

    Returns:
        None
    """
    house_id = ObjectId(house_id)
    house = House.objects(id=house_id).first()
    if not house:
        raise logger(f'Не существует дома с переданным ID')
    meters_ids = AreaMeter.objects(
        area__house__id=house_id,
        readings__0__exists=True,
        readings__period=None,
        _type='AreaMeter',
    ).distinct('id')
    if not meters_ids:
        raise logger(
            f'В доме не обнаружены счетчики с некорректным показанием'
        )
    logger(f'Найдено счётчиков c некорректным показанием: {len(meters_ids)}')
    CustomScriptData(
        task=task.id if task else None,
        coll='Meter',
        data=list(AreaMeter.objects(id__in=meters_ids).as_pymongo())
    ).save()
    deleted_count = 0
    for meter_id in meters_ids:
        meter = AreaMeter.objects(id=meter_id).first()
        logger(f'Счетчик: {meter.serial_number}. '
               f'Помещение: {meter.area.str_number}')
        readings = meter.readings
        readings = [reading for reading in readings if 'period' in reading]
        deleted_count += len(meter.readings) - len(readings)
        AreaMeter.objects(id=meter_id).update(readings=readings)
    logger(f'Удалено показаний: {deleted_count}')
