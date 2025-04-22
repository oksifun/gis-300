import copy
from datetime import datetime

from dateutil.relativedelta import relativedelta

from mongoengine import Q

from app.area.models.area import Area
from app.caching.core.utils import parse_str_number_list, parse_number_list
from app.house.models.house import House
from app.meters.models.meter import AreaMeter

from lib.dates import start_of_month

from processing.models.billing.account import Tenant
from processing.models.billing.coefficient import Coefficient


def filter_accounts(
        accounts_ids,
        filter_params,
        house_id=None,
        binds=None,
        date_on=None,
        date_from=None,
        for_report=False
):
    if not date_on:
        date_on = datetime.now()
    params = copy.copy(filter_params)
    if params.get('areas_str'):
        params['areas_list'] = parse_str_number_list(params['areas_str'])
    else:
        params['areas_list'] = None
    if params.get('porches_str'):
        params['porches_list'] = parse_number_list(params['porches_str'])
    else:
        params['porches_list'] = None
    account_data = _get_accounts(params, accounts_ids, house_id, binds)
    # Фильтруем по льготникам, если требуется
    if params.get('only_privileged'):
        # TODO: Костыль, который позволяет отделить фильтрацию по льготникам в
        #  отчетах от фильтрации в создании начислений
        account_data = _filter_by_privileges(params, account_data, for_report)
    # Фильтруем лицевые счета по подъездам
    account_data = _filter_by_porches_and_area_params(
        params,
        account_data,
        date_on,
    )
    # Фильтрация по ЛС по счетчикам
    account_data = _filter_by_meters(params, account_data, date_on)
    # Фильтрация по признаку квартиры
    account_data = _filter_by_area_sign(params, account_data, date_on, date_from)
    # Фильтрация по коэффициенту квартиры
    account_data = _filter_by_area_coefficient(params, account_data, date_on)
    return list(account_data)


def _get_accounts(params, accounts_ids, house_id, binds):
    """
    Подтягиваем данные аккаунтов
    :param accounts_ids: list
    :return: list
    """
    account_query = {'is_deleted': {'$ne': True}}
    if accounts_ids is not None:
        account_query['_id'] = {'$in': accounts_ids}
    elif not house_id:
        raise ValueError('Filter needs accounts or house')
    if house_id:
        account_query['area.house._id'] = house_id
    if binds:
        account_query.update(Tenant.get_binds_query(binds, raw=True))
    if params.get('property_types') is not None:
        account_query['statuses.ownership.type'] = \
            {'$in': params.get('property_types')}
    if params.get('area_types') is not None:
        account_query['area._type'] = {'$in': params.get('area_types')}
    if params.get('account_types') is not None:
        account_query['_type'] = params.get('account_types')
    if params.get('is_developer'):
        account_query['is_developer'] = True
    elif params.get('is_developer') is False:
        account_query['is_developer'] = {'$ne': True}
    if params.get('areas_list') is not None:
        account_query.update({
            'area.str_number': {'$in': params.get('areas_list')}
        })
    account_data = Tenant.objects(
        __raw__=account_query,
    ).only(
        'id',
        'area',
        'coefs',
        'short_name',
        'str_name',
        'number',
        'phones',
    ).as_pymongo()

    return list(account_data)


def _extract_devices(area, device_type, date_on):
    """
    Извлекаем все радио/антенны из комнат,
    которые удовлетворяют дате и сортируем
    :param area: квартира
    :param device_type: варианты: antenna_count / radio_count
    :return: сортированный список значений
    """
    # Извлекаем все радио из комнат,
    # которые удовлетворяют дате,
    # сортируем и берем ближайшую последнюю
    devices = [radio for room in area.get('rooms', [])
               for radio in room.get(device_type, [])
               if radio['date'] < date_on]
    if not devices:
        return
    # Суммируем значения value по комнатам за одну и ту же дату
    devices = list(
        map(lambda date: dict(date=date,
                              value=sum([v['value']
                                         for v in devices
                                         if v['date'] == date])),
            list(set([x['date'] for x in devices])))
    )
    devices.sort(key=lambda x: x['date'])
    return devices


def _filter_by_porches_and_area_params(params, account_data, date_on):
    """
    Фильтрация ЛС по подъездам, лифту, антенне, радио
    :param account_data: list - лицевые счета
    :return: list - отфильтрованный по подъездам список ЛС
    """

    area_attributes = any([
        True
        for x in (
            params.get('lift'),
            params.get('radio'),
            params.get('antenna')
        )
        if x is not None
    ])
    if not params.get('porches_list') and not area_attributes:
        return account_data

    area_query = Q(id__in=[x['area']['_id'] for x in account_data])

    # Если нужен фильтр по подъездам
    if params.get('porches_list'):
        house = House.objects(pk=params.get('house')).get()
        porches_ids = [
            x.id
            for x in house.porches
            if x.number in params.get('porches_list')
        ]
        area_query &= Q(porch__in=porches_ids)

    # Фильтр по лифту
    if params.get('lift') is not None:
        area_query &= Q(has_lift=params.get('lift'))

    filtered_areas = Area.objects(area_query).only(
        'id', 'rooms', 'has_lift'
    ).as_pymongo()

    # Применим фильтры по антенне и радио по offsets_date_to или
    # ближайшей меньшей дате
    if params.get('radio') is not None or params.get('antenna') is not None:
        # Айди будущих подошедших квартир
        radio_filter, antenna_filter = set(), set()
        has_radio_query = params.get('radio')
        has_antenna_query = params.get('antenna')
        for area in filtered_areas:
            if has_radio_query is not None:
                # Извлекаем все радио из комнат,
                # которые удовлетворяют дате,
                # сортируем и берем ближайшую последнюю
                radios = _extract_devices(area, 'radio_count', date_on)
                has_radio = False if not radios else radios[-1]['value'] > 0
                if has_radio is has_radio_query:
                    radio_filter.add(area['_id'])
            if has_antenna_query is not None:
                # Извлекаем все антенны из комнат,
                # которые удовлетворяют дате,
                # сортируем и берем ближайшую последнюю
                antennas = _extract_devices(area, 'antenna_count', date_on)
                has_antenna = False if not antennas \
                    else antennas[-1]['value'] > 0
                if has_antenna is has_antenna_query:
                    antenna_filter.add(area['_id'])
        # Фильтруем
        if has_antenna_query is None and has_radio_query is not None:
            additional_filters = radio_filter
        elif has_antenna_query is not None and has_radio_query is None:
            additional_filters = antenna_filter
        else:
            additional_filters = radio_filter & antenna_filter
        account_data = [x for x in account_data
                        if x['area']['_id'] in additional_filters]
    else:
        filtered_areas = [x['_id'] for x in filtered_areas]
        account_data = [x for x in account_data
                        if x['area']['_id'] in filtered_areas]
    return account_data


def _filter_by_meters(params, account_data, date_on):
    """
    Фильтрация ЛС по наличию счетчиков определенного типа
    :param account_data: list
    :return: list: измененный account_data
    """
    meter_types = (
        (params.get('cold_water_meter'), ['ColdWaterAreaMeter']),
        (params.get('hot_water_meter'), ['HotWaterAreaMeter']),
        (params.get('gas_meter'), ['GasRateAreaMeter']),
        (
            params.get('electric_meter'),
            [
                'ElectricOneRateAreaMeter',
                'ElectricTwoRateAreaMeter',
                'ElectricThreeRateAreaMeter',
            ],
        ),
        (params.get('heat_meter'), ['HeatAreaMeter'])
    )
    # Если хотя бы один есть из фильтров
    if not any([True for x in meter_types if x[0] is not None]):
        return account_data

    # Формирование запроса по фильтру + только активные счетчики
    # (working_finish_date которых больше текущей даты или не задан)
    meters_query = (
            Q(area__id__in=[x['area']['_id'] for x in account_data])
            & Q(is_deleted__ne=True)
            & (Q(working_finish_date__gte=date_on)
               | Q(working_finish_date=None))
    )
    is_true = []
    is_false = []
    for is_type, type_list in meter_types:
        if is_type is True:
            is_true.extend(type_list)
        elif is_type is False:
            is_false.extend(type_list)

    meters_filter = AreaMeter.objects(
        meters_query).only('area.id', '_type').as_pymongo()
    # Собираем типы счетчиков для каждой квартиры
    area_meter_groups = {}
    for meter in meters_filter:
        area_group = area_meter_groups.setdefault(meter['area']['_id'], [])
        meter['_type'].remove('AreaMeter')
        if meter['_type'][0] not in area_group:
            area_group.extend(meter['_type'])

    def meter_type_filter(area_id):
        """
        Проверяем, что типы счетчиков в квартире удовлетворяют фильтру
        :param area_id: id квартиры
        :return: bool
        """
        # Список типов счетчиков квартиры
        a_meter_types = area_meter_groups.get(area_id, [])
        if is_true:
            # Убедимся, что все счетчики из требуемого листа
            # входят в квартиру
            if not all(map(lambda x: x in a_meter_types, is_true)):
                return False
        if is_false:
            # Убедимся, что ни один счетчик квартиры
            # не входит в запрещенный лист
            if any(map(lambda x: x in a_meter_types, is_false)):
                return False
        return True

    # Фильтруем ЛС
    account_data = [
        x for x in account_data
        if meter_type_filter(x['area']['_id'])
    ]

    return account_data


def _filter_by_sign_or_coefficient(account_data,
                                   filter_id,
                                   filter_state,
                                   date_on,
                                   date_from=None):
    """
    Фильтрация ЛС по квартирному коэффициенту или признаку
    :param account_data: list - данные аккаунтов
    :param filter_id: id коэф-а или признака
    :param filter_state: bool
    :return: new_account_data: list - отфильтрованные ЛС
    """
    coeff = Coefficient.objects(
        id=filter_id,
    ).only(
        'id',
        'is_feat',
        'is_once',
        'default',
    ).as_pymongo().first()
    if not coeff:
        return account_data
    if coeff.get('is_feat'):
        is_default = bool(coeff['default']) == filter_state
    else:
        is_default = coeff['default'] == filter_state

    new_account_data = []

    month = date_on.replace(day=1)
    for acc in account_data:
        if not acc.get('coefs'):
            if is_default:
                new_account_data.append(acc)

        # Если коэффициент есть среди коэф-ов ЛС
        elif filter_id in {c['coef'] for c in acc['coefs']}:
            # значение коэф-а по умолчанию
            acc_coefs = sorted(
                acc['coefs'],
                key=lambda x: x['period'],
                reverse=True
            )
            if coeff['is_once']:
                # нужно искать значение за конкретный месяц
                # или брать значение по умолчанию
                value_gen = (
                    a_c['value']
                    for a_c in acc_coefs
                    if filter_id == a_c['coef'] and month == a_c['period']
                )
            else:
                if date_from:
                    matched = False
                    for a_c in acc_coefs:
                        # Если в периоде coef-value был положительный
                        if filter_id == a_c['coef'] and \
                                date_on >= a_c['period'] >= \
                                date_from.replace(day=1) and bool(a_c['value']):
                            value_gen = a_c['value']
                            matched = True
                            break
                        # Если на начало периода coef-value был нулевой
                        elif filter_id == a_c['coef'] and \
                                date_from.replace(day=1) == a_c['period']:
                            value_gen = a_c['value']
                            matched = True
                            break
                    # Если не найдено в переданный период coef-value
                    if not matched:
                        value_gen = (
                            a_c['value']
                            for a_c in acc_coefs
                            if filter_id == a_c['coef'] and
                               date_from.replace(day=1) > a_c['period']
                        )
                # брать ближайшее раннее значение или значение по умолчанию
                else:
                    value_gen = (
                        a_c['value']
                        for a_c in acc_coefs
                        if filter_id == a_c['coef'] and date_on >= a_c['period']
                    )
            if date_from and matched:
                value = value_gen
            else:
                value = next(value_gen, coeff['default'])

            if coeff.get('is_feat'):
                value = bool(value)
            # Фильтруем по условиям
            if filter_state == value:
                new_account_data.append(acc)
        elif is_default:
            new_account_data.append(acc)

    return new_account_data


def _filter_by_area_sign(params, account_data, date_on, date_from=None):
    """
    Фильтрация ЛС по признаку
    :param account_data: list
    :return: list: измененный account_data
    """
    if None in {params.get('feat'), params.get('feat_value')}:
        return account_data

    return _filter_by_sign_or_coefficient(
        account_data,
        params.get('feat'),
        params.get('feat_value'),
        date_on,
        date_from
    )


def _filter_by_area_coefficient(params, account_data, date_on):
    """
    Фильтрация ЛС по квартирному коэффициенту
    :param account_data: list
    :return: list: измененный account_data
    """
    if (
            params.get('coef') is None
            or not params.get('coef_value')
    ):
        return account_data

    return _filter_by_sign_or_coefficient(
        account_data,
        params.get('coef'),
        params.get('coef_value'),
        date_on,
    )


def _filter_by_privileges(params, account_data, for_report=False):
    account_ids = [account['_id'] for account in account_data]
    query = {'_id': {'$in': account_ids}, 'is_privileged': True}
    if not for_report:
        date_from = params.get('date_from')
        date_till = params.get('date_till')
        if not all((date_till, date_from)):
            month = params.get('responsible_month')
            date_from = start_of_month(month)
            date_till = date_from + relativedelta(months=1)
        query.update(
            {
                'statuses.registration': {
                    '$elemMatch': {
                        '$and': [
                            {'$or': [
                                {'date_from': {'$lte': date_till}},
                                {'date_from': None}
                            ]},
                            {'$or': [
                                {'date_till': {'$gte': date_from}},
                                {'date_till': None}
                            ]}
                        ]
                    }
                }
            }
        )
    tenants = Tenant.objects(__raw__=query).as_pymongo().distinct('id')
    account_data = [
        account for account in account_data if account['_id'] in tenants
    ]
    return account_data
