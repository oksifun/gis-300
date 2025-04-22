from datetime import datetime

from app.meters.models.meter import AreaMeter
from lib.dates import months_between
from dateutil.relativedelta import relativedelta


def get_meters(areas, month, postponement=0):
    """
    Сбор данных со счетчиков
    :param postponement: какое то смещение для увеличения
                         периода определения активных счетчиков
    :param areas: list: квартиры (необходимы только 'id' и 'communications'))
    :param month: datetime object: Месяц показаний
    :return: список словарей [{квартира: {ресурс: {}, ...}}, ...]
    """
    month = make_month_from(month)
    result = {}
    resources = {
        'cold_water': 'ColdWaterAreaMeter',
        'hot_water': 'HotWaterAreaMeter',
        'electricity_regular': 'ElectricOneRateAreaMeter',
        'electricity_two_rate': 'ElectricTwoRateAreaMeter',
        'electricity_three_rate': 'ElectricThreeRateAreaMeter',
        'heat': 'HeatAreaMeter',
        'gas': 'GasAreaMeter'
    }
    areas_ids = [x['_id'] for x in areas]

    all_meters = AreaMeter.objects(
        __raw__={'area._id': {'$in': areas_ids}, 'is_deleted': {'$ne': True}}
    ).only(
        'readings',
        'area.id',
        'serial_number',
        '_type',
        'working_start_date',
        'reverse',
        'working_finish_date',
        'is_deleted',
        'initial_values',
        'order',
    ).as_pymongo()
    # Сгруппируем по квартирам счетчики
    grouped_meters = {}
    for x in all_meters:
        area_meters = grouped_meters.setdefault(x['area']['_id'], [])
        area_meters.append(x)

    if not grouped_meters:
        return {}

    for area in areas:
        # Будущие ресурсы помещения
        resources_dict = {}
        area_meters = grouped_meters.get(area['_id'])
        if not area_meters:
            # Если нет счетчиков
            continue
        # Добыча данных по типу ресурса
        for resource in resources.keys():
            # Все счетчики этого типа ресурса
            res_meters = [
                x for x in area_meters
                if ((resources[resource] in x['_type'])
                    and x['working_start_date']
                    and make_month_from(x['working_start_date']) <= month)
            ]
            if not res_meters:
                # resources_dict.update({resource: {}})
                continue
            # 1. Объем за текущий период
            # объем по всем счетчикам этого ресурса
            volumes = [_get_volume(x, month) for x in res_meters]
            # сумма сданного объема по всем счетчикам
            volume = _sum_volumes(volumes)

            # 2. Средний объем по каждому тарифу
            average_volumes = _get_average_by_tariffs(res_meters, month)

            # 3. Сданы ли показания за текущий период?
            readings_is_taken = True if volume else False

            # 4. Показания сдавались когда-нибудь?
            readings_exists = any(
                [_check_readings(x, month) for x in res_meters]
            )
            # 5. Разрыв месяцев последней замены. Если после завершения
            #    эксплуатации счетчика, до момента установки нового счетчика
            #    прошло более месяца
            rift = _get_last_rift(res_meters,
                                  month)

            # 6. Сколько месяцев прошло с момента последней сдачи показаний
            month_from_last_reading = _get_last_reading_spread(res_meters,
                                                               rift,
                                                               month)
            # Наличие активных счетчиков
            a_meters = []
            for meter in res_meters:
                if make_month_from(meter['working_start_date']) <= month:
                    meter['is_active'] = \
                        (meter.get('working_finish_date') or month) >= month
                    a_meters.append(
                        meter['working_finish_date']
                        + relativedelta(months=postponement)
                        if meter.get('working_finish_date') else None
                    )
                else:
                    meter['is_active'] = False
            # Если нет активных счетчиков, то не опредляем ближайшую дату учета
            if None in a_meters or list(filter(lambda x: x >= month, a_meters)):
                # 7. Месяц начала учета ближайшего счетчика.
                # 8. День начала учета ближайшего счетчика
                nearest_start_month, nearest_start_day = _get_nearest_meter_date(
                    res_meters, rift, month
                )
            # Если счетчики закрыты
            else:
                nearest_start_month = None
                nearest_start_day = None
            # 9. Список счетчиков с текущими показаниями
            meters_readings_list = _get_meters_with_readings(res_meters, month)

            # 10. Последняя дата окончания учета счетчика
            last_finish_date = _get_last_finish_date(res_meters,
                                                     month,
                                                     postponement)

            area_resource = dict(
                readings_is_taken=readings_is_taken,
                readings_exists=readings_exists,
                month_from_last_reading=month_from_last_reading,
                nearest_start_month=nearest_start_month,
                nearest_start_day=nearest_start_day,
                rift=rift[0],
                meters_readings_list=meters_readings_list,
                last_finish_date=last_finish_date
            )
            # Добавление данных в соответствии с тарифностью счетчиков
            meter_types = list(
                {[t for t in meter['_type'] if t != 'AreaMeter'][0]
                 for meter in res_meters}
            )
            area_resource = _add_values_by_tariff(area_resource=area_resource,
                                                  volume=volume,
                                                  average_volume=average_volumes,
                                                  meter_types=meter_types)

            # Добавим данные в словарь и его в результат
            if not area_resource:
                resources_dict.update({resource: {}})
            else:
                for res in area_resource:
                    res_name, res_params = list(res.items())[0]
                    resources_dict.update(
                        {(resource
                          if res_name == 'one_rate'
                          else res_name): res_params}
                    )

        result.update({area['_id']: resources_dict})
    return result


def not_entry_period(m1_working_start_date,
                     m1_working_finish_date,
                     m2_working_finish_date,
                     m2_working_start_date):
    """
    Проверка вхождения пары периодов
    :param m1_working_start_date: начало первого периода
    :param m1_working_finish_date: конец первого периода
    :param m2_working_start_date: начало второго периода
    :param m2_working_finish_date: конец второго периода
    :return: bool: True, если не входят в периоды работы
    """
    # None заменяем на 2100 год (уходит в бесконечность)
    return (m1_working_start_date >= (m2_working_finish_date
                                      or datetime(2100, 1, 1))
            or (m1_working_finish_date
                or datetime(2100, 1, 1)) <= m2_working_start_date)


def not_entry_point(m_working_start_date,
                    m_working_finish_date,
                    rift_point):
    """
    Временная точка не входит в период
    :param m_working_start_date: начало первого периода
    :param m_working_finish_date: конец первого периода
    :param rift_point: точка разрыва
    :return: bool: True, если не входят в периоды работы
    """
    # None заменяем на 2100 год (уходит в бесконечность)
    return not (m_working_start_date <= rift_point <= (m_working_finish_date
                                                       or datetime(2100, 1, 1)))


def make_month_from(date):
    """
    Превращение даты в 'месяц'
    :param date: datetime: дата
    :return: datetime: год и месяц
    """
    return date.replace(day=1,
                        hour=0,
                        minute=0,
                        second=0,
                        microsecond=0)


def _get_volume(meter, month=None):
    """
    Объем счетчика за текущий период
    :param meter: счетчик
    :param month: интересующий период
    :return: list: объем счетчика. Например, [3] или [2, 4] и т.д.
                   в зависимости от тарифности счетчика
    """
    month = month or make_month_from(datetime.now())
    for reading in meter['readings']:
        if reading['period'] == month:
            return reading['deltas']
    return


def _sum_volumes(volumes):
    """
    Суммирование объемов по счетчикам в зависимости
    от их тарифности
    :param volumes: list: список из списков с объемами за период
    :return: list: список со списком просуммированных объемов для тарифов
    """
    volumes = [x for x in volumes if x]
    # Все возможные варианты тарифных счетчиков
    tariff_count = (([x for x in volumes if len(x) == 1], 1),
                    ([x for x in volumes if len(x) == 2], 2),
                    ([x for x in volumes if len(x) == 3], 3))
    result = []
    for tar in tariff_count:
        if tar[0]:
            # Суммирование объемов по тарифам
            tar_value = [sum([x[i] for x in tar[0]]) for i in range(tar[1])]
            result.append(tar_value)
    return result


def _get_average_value(meters, month):
    """
    Средний объем
    :param meters: счетчики только одного типа (например, двухтарифные)
    :param month: datetime: период
    :return: list: список среднего объема по каждому тарифу, если есть
    """
    result = []
    all_reading_list = []
    for m in meters:
        all_reading_list.extend(m['readings'])

    # Сложение значений со счетчиков, сданные за один период
    # Уникальные периоды
    unique_readings = {}
    # Суммирование объемов за период
    for r in all_reading_list:
        delta = unique_readings.setdefault(r['period'], None)
        if delta:
            unique_readings[r['period']] = list(
                map(lambda x, y: x + y, r['deltas'], delta)
            )
        else:
            unique_readings[r['period']] = r['deltas']
    all_reading_list = [
        {'period': x, 'deltas': unique_readings[x]}
        for x in unique_readings
    ]

    # Последний месяц, в который сдавались показания
    # или текущий месяц
    last_reading = [
        x['period'] for x in all_reading_list if x['period'] <= month
    ]
    if not last_reading:
        return
    last_reading.sort()
    last_reading = last_reading[-1]
    # Последние 12 месяцев от последнего месяца сдачи показаний
    date_limit = last_reading.replace(year=last_reading.year - 1)
    # Релевантные показания
    readings = [x for x in all_reading_list
                if date_limit < x['period'] <= last_reading]
    readings.sort(key=lambda x: x['period'], reverse=True)

    # Проверка периода за который считается среднее, если
    # период начинается с первого показания
    extra_period = None
    # Дата первого показания
    first_reading = sorted([x['period'] for x in all_reading_list])[0]
    # Если началом периода является первое показание
    if not (readings[-1]['period'] > first_reading):
        # Поиск w_s_d и w_f_d раньше первого периода сдачи показаний
        extra_period = []
        for m in meters:
            extra_period.append(m['working_start_date'])
            if m.get('working_finish_date'):
                extra_period.append(m['working_finish_date'])
        extra_period = [p for p in extra_period if p < readings[-1]['period']]
        if extra_period:
            extra_period.sort()
            extra_period = months_between(
                extra_period[0], readings[-1]['period']
            ) - 1
    # Если начало периода не первое показание, но в периоде меньше 12 показаний
    elif (readings[-1]['period'] > first_reading) and len(readings) < 12:
        extra_period = 12 - len(readings)

    # Доп. проверка todo скорее всего не нужна
    # Берем последнии 12 месяцев
    if len(readings) > 12:
        readings = readings[:12]

    # Объемы за каждый период
    deltas = [x['deltas'] for x in readings]
    if not deltas:
        return
    # Знаменатель для среднего
    denominator = months_between(readings[-1]['period'], readings[0]['period'])
    # Прибавим период, за который показания не сдавались, но счетчик работал,
    # но не более 12 месяцев
    denominator = denominator + extra_period if extra_period else denominator
    # Но не более 12 месяцев
    denominator = 12 if denominator > 12 else denominator
    # Суммирование по каждому тарифу ресурса отдельно, если их несколько
    for i in range(len(deltas[0])):
        # Все объемы тарифа
        tar_value = [x[i] for x in deltas]
        result.append(sum(tar_value)/denominator)
    return result


def _get_average_by_tariffs(meters, month):
    """
    Среднее по всем тарифам
    :param meters: список всех счетчиков одного типа ресурса (вода, например)
                   с любыми тарифными показаниями
    :param month: период
    :return: list: Списки среднего для каждого тарифа
    """
    # Разделение по типам счетчиков
    separated_meters = [[m for m in meters
                         if ((len(m['readings'][0]['deltas'])
                              if m.get('readings')
                              else 1) == tar_len + 1)]
                        for tar_len in range(3)]
    # Средний объем с каждой группы счетчиков
    result = [_get_average_value(x, month) for x in separated_meters if x]
    result = [x for x in result if x]
    return result


def _check_readings(meter, month):
    """
    Показания сдавались когда-нибудь?
    :return: bool: True, если сдавались
    """
    if [True for r in meter['readings'] if r['period'] <= month]:
        return True
    else:
        return False


def _get_last_reading_spread(meters, rift, month=None):
    """
    Сколько месяцев прошло, с момента последней сдачи показаний до разрыва
    :param meters: list: счетчики
    :param rift: tuple: (факт расхождения,
                         дата учета счетчика после расхождения)
    :param month: интересующий период
    :return: datetime или None
    """
    month = month or make_month_from(datetime.now())

    if rift[0]:
        # Период разрыва, если он был
        rift_date = make_month_from(rift[1])

    # Если не было разрывов или учет следующего счетчика
    # последнего разрыва идет после интересующего периода
    if not rift[0] or month < rift_date:
        # Последнии показания из каждого счетчика
        meters_last_periods = map(lambda m: max([r['period']
                                                 for r in m['readings']
                                                 if r['period'] < month],
                                                default=None),
                                  meters)
        # Самое последние показание среди все показаний
        last_period = max([x for x in meters_last_periods if x], default=False)

    else:
        low_limit = rift_date
        # Последнии показания из каждого счетчика
        meters_last_periods = map(lambda m: max([r['period']
                                                 for r in m['readings']
                                                 if (low_limit
                                                     <= r['period'] < month)],
                                                default=None),
                                  meters)
        # Самое последние показание среди все показаний
        last_period = max([x for x in meters_last_periods if x], default=False)

    # Если показаний не оказалось
    if not last_period:
        # Ищем активные счетчики у которых в текущий момент есть показания
        # и берем их даты начала учета
        active_meters_starts_dates = [
            x['working_start_date'] for x in meters
            if (make_month_from(x['working_start_date']) <= month
                and any([True for r in x['readings'] if r['period'] == month]))
        ]
        if active_meters_starts_dates:
            last_period = min(active_meters_starts_dates)
        else:
            last_period = max(
                [x['working_start_date'] for x in meters
                 if make_month_from(x['working_start_date']) <= month],
                default=False
            )
        # Если дата учета позже периода запроса
        if not last_period:
            return
        last_period = make_month_from(last_period) - relativedelta(months=1)

    spread = relativedelta(month, make_month_from(last_period))
    return spread.months + spread.years * 12


def _get_nearest_meter_date(meters, rift, month=None):
    """
    Месяц и день начала учета ближайшего счетчика
    после разрыва
    :param meters: list: счетчики
    :param rift: tuple: (факт расхождения, дата последнего расхождения)
    :param month: интересующий период
    :return: tuple: (месяц, день)
    """
    month = month or make_month_from(datetime.now())
    month_only = True
    # Если не было разрыва в месяцах
    if not rift[0]:
        # Ищем дату начала работы счетчика включая текущий месяц
        meter_dates = [x['working_start_date'] for x in meters
                       if make_month_from(x['working_start_date']) <= month]
    # Был разрыв в месяцах
    else:
        meter_dates = [rift[1]]
    # Если нет данных
    if not meter_dates:
        return None, None
    # Самая последняя дата начал учета
    nearest_date = max(meter_dates)

    # Блок проверяет нет ли разрыва хотя бы в день между установкой счетчиков
    # чтобы определить в каком формате возвращать месяц и день разрыва
    # Последняя дата конца учета
    last_finish_date = [
        x['working_finish_date']
        for x in meters
        if (
            x.get('working_finish_date')
            and x['working_finish_date'] <= nearest_date
        )
    ]
    if last_finish_date:
        last_finish_date = max(last_finish_date)
        days_rift = relativedelta(nearest_date, last_finish_date)
        if days_rift.days > 0 or days_rift.months > 0 or days_rift.years > 0:
            month_only = False
    else:
        month_only = False

    if not month_only:
        return make_month_from(nearest_date), nearest_date.day
    else:
        return make_month_from(nearest_date), 1


def _get_last_finish_date(meters, month, postponement):
    """
    Последния дата окончания учета счетчика
    :param meters: list: счетчики
    :param postponement: int: период, который мы еще учитываем че-то по счетчику
                              хоть он уже и закрыт
    :param month: интересующий период
    :return: datetime: дата окончания учета
    """
    # postponement нужно прибавлять только к завершенному последнему счетчику,
    # значит если есть незавершенные приборы, то прибавлять не нужно,
    # т.к. завершенные счетчики не могут быть последними
    if None in [x.get('working_finish_date') for x in meters]:
        postponement = 0
    meter_dates = [
        x['working_finish_date'] for x in meters
        if (x.get('working_finish_date')
            and x['working_finish_date']
            + relativedelta(months=postponement) <= month)
    ]
    # Если нет данных
    if not meter_dates:
        return
    last_date = max(meter_dates)
    return last_date


def _get_last_rift(meters, month):
    """
    Разрыв месяцев последней замены. Если после завершения
    эксплуатации счетчика, до момента установки нового счетчика
    прошло более месяца
    Если счетчик является первым, вернется True
    :return tuple: (был ли разрыв, дата учета счетчика после разрыва)
    """

    def get_rift_from(meter_list):
        """
        Получение разрыва замены из переданного списка счетчиков
        :param meter_list: список счетчиков
        :return: tuple: (был ли разрыв, дата учета счетчика после разрыва)
        """
        # Если счетчик один или ни одного
        if len(meter_list) < 2:
            return False
        meter_list.sort(
            key=lambda x: x.get('working_finish_date') or datetime.max,
            reverse=True,
        )
        for i in range(len(meter_list) - 1):
            # Дата начала работы счетчика
            start_meter_date = make_month_from(
                meter_list[i]['working_start_date']
            )
            # Дата окончания учета предыдущего
            finish_meter_date = meter_list[i + 1].get('working_finish_date')
            # Если предыдущий счетчик не имеет дату окончания
            # (например, счетчик рабочий с другого стояка),
            # то не оставляем None, сравнение ничего не даст
            # и разрыв не будет считаться
            finish_meter_date = (make_month_from(finish_meter_date)
                                 if finish_meter_date
                                 else finish_meter_date)
            rift = relativedelta(start_meter_date, finish_meter_date)
            # Получаем разницу ПЕРИОДОВ между установкой нового
            # и окончанием старого
            if rift.months > 1 or rift.years:
                # Берем день назад от учета последнего счетчика после разрыва,
                # чтобы выяснить нет ли пересечений в работе с другими
                # счетчиками, и чтобы в сравнение не попадал счетчик учета
                rift_point = start_meter_date - relativedelta(days=1)
                if all([not_entry_point(x[0], x[1], rift_point) for x in
                        meters_work_periods]):
                    return True, start_meter_date
                else:
                    return False
        return False

    # Рабочие периоды счетчиков
    meters_work_periods = [(x['working_start_date'],
                            x.get('working_finish_date'))
                           for x in meters]
    # Блок проверяет, является ли активный счетчик первым и единственным
    # если да - считаем это как разрыв
    # (если сразу несколько счетчикок введено в эксплуатацию в одно время
    # считаем как по одному)
    if meters_work_periods:
        # Самая ранняя дата начала учета среди счетчиков,
        # которые сейчас работают
        # Поиск активных периодов начала учета
        active_dates = list({x[0] for x in meters_work_periods
                             if not not_entry_point(x[0], x[1], month)})
        if active_dates and len(active_dates) == 1:
            start_active_date = min(active_dates)
            # Если есть текущий счетчик и он первый, сразу возвращаем как разрыв
            if not [1 for x in meters
                    if x['working_start_date'] < start_active_date]:
                return True, start_active_date

    # Разделение анализирования по направлениям работы счетчиков
    direct_meters = [x for x in meters if x['reverse'] is False]
    reverse_meters = [x for x in meters if x['reverse'] is True]
    # Получение разрывов для двух направлений счетчиков
    all_rifts = [get_rift_from(x) for x in (direct_meters, reverse_meters)]
    # Разрывы по всем счетчикам
    all_rifts = [x for x in all_rifts if x]
    # Последний разрыв
    last_rift = (max(all_rifts, key=lambda x: x[1])
                 if all_rifts
                 else (False, None))
    return last_rift[0], last_rift[1]


def _get_meters_with_readings(meters, month):
    """
    Список счетчиков с текущими показаниями
    :param meters: список счетчиков
    :return: list: счетчики с серийным номером и текущими показаниями
    """
    result = []
    for meter in meters:
        # Последнее, оно же текущее показание счетчика
        if not meter['is_active']:
            continue
        data = {
            'serial_number': meter['serial_number'],
            'current': None,
            'prev': meter['initial_values'],
        }
        for readings in reversed(meter['readings']):
            if readings['period'] == month:
                data['current'] = readings['values']
            elif readings['period'] < month:
                data['prev'] = readings['values']
                break
        result.append(data)
    return result


def _add_values_by_tariff(area_resource, volume, average_volume, meter_types):
    """

    :param area_resource: Словарь в который нужно добавить данные
    :param volume: список показаний по объему
    :param average_volume: список показаний по среднему объему
    :param meter_types: тип счетчика
    :return: area_resource и новые ресурсы
    """
    # Копия данных
    new_resource = {k: v for k, v in area_resource.items()}
    # Список новых ресурсов
    new_res_list = []
    # Тарифы
    tars_dict = {
        'ElectricTwoRateAreaMeter': 2,
        'ElectricThreeRateAreaMeter': 3
    }
    # Типы счетчиков по тарифности
    tar_count = [tars_dict.get(x, 1) for x in meter_types]
    # Получение значений соответсвующих счетчиков и
    # добавление соответсвующего ресурса
    for tar_rate in tar_count:
        if tar_rate == 1:
            volume_tar_1 = volume[0][0] if volume else 0
            average_volume_tar_1 = (average_volume[0][0]
                                    if average_volume
                                    else 0)
            one_rate = dict(volume=volume_tar_1,
                            average_volume=(average_volume_tar_1
                                            if average_volume_tar_1 > 0
                                            else 0))
            one_rate.update(new_resource)
            new_res_list.append({'one_rate': one_rate})
        elif tar_rate == 2:
            # Двухтарифный
            volume_tar_2 = [x for x in volume if len(x) == 2]
            average_volume_tar_2 = [x for x in average_volume
                                    if len(x) == 2]
            # Тарифы
            volume_day = volume_tar_2[0][0] if volume_tar_2 else 0
            volume_night = volume_tar_2[0][1] if volume_tar_2 else 0

            average_volume_day = (average_volume_tar_2[0][0]
                                  if average_volume_tar_2
                                  else 0)
            average_volume_night = (average_volume_tar_2[0][1]
                                    if average_volume_tar_2
                                    else 0)
            # День
            peak = dict(volume=volume_day,
                        average_volume=(average_volume_day
                                        if average_volume_day > 0
                                        else 0))
            peak.update(new_resource)
            new_res_list.append({'electricity_day': peak})
            # Ночь
            night = dict(volume=volume_night,
                         average_volume=(average_volume_night
                                         if average_volume_night > 0
                                         else 0))
            night.update(new_resource)
            new_res_list.append({'electricity_night': night})
        elif tar_rate == 3:
            # Трехтарифный
            volume_tar_3 = [x for x in volume if len(x) == 3]
            average_volume_tar_3 = [x for x in average_volume
                                    if len(x) == 3]
            # Тарифы
            volume_peak = volume_tar_3[0][0] if volume_tar_3 else 0
            volume_night = volume_tar_3[0][1] if volume_tar_3 else 0
            volume_semi_peak = volume_tar_3[0][2] if volume_tar_3 else 0

            average_volume_peak = (average_volume_tar_3[0][0]
                                   if average_volume_tar_3
                                   else 0)
            average_volume_night = (average_volume_tar_3[0][1]
                                    if average_volume_tar_3
                                    else 0)
            average_volume_semi_peak = (average_volume_tar_3[0][2]
                                        if average_volume_tar_3
                                        else 0)

            # Пик
            peak = dict(volume=volume_peak,
                        average_volume=(average_volume_peak
                                        if average_volume_peak > 0
                                        else 0))
            peak.update(new_resource)
            new_res_list.append({'electricity_peak': peak})
            # Ночь
            night = dict(volume=volume_night,
                         average_volume=(average_volume_night
                                         if average_volume_night > 0
                                         else 0))
            night.update(new_resource)
            new_res_list.append({'electricity_night': night})
            # Полупик
            semi_peak = dict(volume=volume_semi_peak,
                             average_volume=(average_volume_semi_peak
                                             if average_volume_semi_peak > 0
                                             else 0))
            semi_peak.update(new_resource)
            new_res_list.append({'electricity_semi_peak': semi_peak})

    return new_res_list
