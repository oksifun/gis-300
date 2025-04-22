import datetime

from bson import ObjectId
from dateutil.relativedelta import relativedelta

from processing.data_producers.balance.base import CONDUCTED_STATUSES
from processing.data_producers.export.administration.base import \
    _has_print_service, _get_print_services
from app.house.models.house import House
from processing.models.billing.accrual import Accrual, \
    CONSUMPTION_TYPE_CHOICES_AS_DICT
from app.accruals.models.accrual_document import AccrualDoc
from processing.models.billing.payment import Payment
from processing.models.billing.service_type import ServiceType


def get_print_service_accruals_count(month_from, logger=None, table_print=None):
    providers = AccrualDoc.objects(
        date_from__gte=month_from,
    ).distinct('provider')
    if logger:
        logger(f'Организаций {len(providers)}')
    result = 0
    print_services = _get_print_services()
    for provider in providers:
        if not _has_print_service(provider, print_services):
            continue
        accounts = Accrual.objects(
            owner=provider,
            month__gte=month_from,
        ).distinct('account.id')
        result += len(accounts)
        if logger:
            logger(result)
    if table_print:
        table_print(result)
    return [[result]]


def get_accruals_houses_statistics(date_from, date_till,
                                   logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    accruals = Accrual.objects(
        __raw__={
            'doc.date': {
                '$gte': date_from,
                '$lt': date_till + relativedelta(days=1),
            },
        },
    ).aggregate(
        {
            '$group': {
                '_id': '$account.area.house._id',
                'value': {'$sum': '$value'},
            },
        },
    )
    payments = Payment.objects(
        __raw__={
            'doc.date': {
                '$gte': date_from,
                '$lt': date_till + relativedelta(days=1),
            },
        },
    ).aggregate(
        {
            '$group': {
                '_id': '$account.area.house._id',
                'value': {'$sum': '$value'},
            },
        },
    )
    accruals = {a['_id']: a['value'] for a in accruals}
    payments = {p['_id']: p['value'] for p in payments if p['_id']}
    title_row = [
        'Адрес',
        'Начислено',
        'Оплачено',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    houses = House.objects(
        pk__in=list(
            set(accruals.keys())
            | set(payments.keys())
        ),
    ).only(
        'id',
        'address',
    ).as_pymongo()
    for house in houses:
        row = [
            house['address'],
            '{:.2f}'.format(accruals.get(house['_id'], 0) / 100),
            '{:.2f}'.format(payments.get(house['_id'], 0) / 100),
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def get_heat_statistics(provider_id, house_id, date_from, date_till,
                        doc_status=None,
                        logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    heat_names = {
        ObjectId("526234c0e0e34c4743822338"): 'Отопление',
        ObjectId("526234c0e0e34c4743822326"): 'Отопление МОП',
    }
    services = [
        ObjectId("526234c0e0e34c4743822338"),
        ObjectId("526234c0e0e34c4743822326"),
    ]
    match_query = {
        'owner': provider_id,
        'account.area.house._id': house_id,
        'doc.date': {
            '$gte': date_from,
            '$lt': date_till + relativedelta(days=1),
        },
        'services.service_type': {'$in': services},
        'is_deleted': {'$ne': True},
    }
    if doc_status:
        match_query['doc.status'] = doc_status
    accruals = Accrual.objects(
        __raw__=match_query,
    ).aggregate(
        {
            '$unwind': '$services',
        },
        {
            '$match': {
                'services.service_type': {'$in': services},
            },
        },
        {
            '$group': {
                '_id': {
                    'account': '$account._id',
                    'service': '$services.service_type',
                },
                'value': {
                    '$sum': {
                        '$add': [
                            '$services.value',
                            '$services.totals.recalculations',
                            '$services.totals.shortfalls',
                            '$services.totals.privileges',
                        ],
                    },
                },
                'cons': {
                    '$sum': '$services.consumption',
                },
                'method': {
                    '$first': '$services.method',
                },
                'area_id': {
                    '$first': '$account.area._id',
                },
            },
        },
        {
            '$lookup': {
                'from': 'Account',
                'localField': '_id.account',
                'foreignField': '_id',
                'as': 'account',
            },
        },
        {
            '$unwind': '$account',
        },
        {
            '$lookup': {
                'from': 'Area',
                'localField': 'area_id',
                'foreignField': '_id',
                'as': 'area',
            },
        },
        {
            '$unwind': '$area',
        },
        {
            '$project': {
                'area_num': '$area.str_number',
                'area_sq': '$area.area_common',
                'name': '$account.str_name',
                'number': '$account.number',
                'service': '$_id.service',
                'value': 1,
                'cons': 1,
                'method': 1,
            },
        },
    )
    title_row = [
        'Квартира',
        'Площадь',
        'ФИО',
        'ЛС',
        'Статья',
        'К оплате',
        'Расход',
        'Метод расчета',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for accrual in accruals:
        row = [
            accrual['area_num'],
            '{:.2f}'.format(accrual.get('area_sq', 0)),
            accrual['name'],
            accrual['number'],
            heat_names[accrual['service']],
            '{:.2f}'.format(accrual['value'] / 100),
            '{:.6f}'.format(accrual['cons']),
            CONSUMPTION_TYPE_CHOICES_AS_DICT[accrual['method']],
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def get_communal_accruals_by_provider(provider_id, month_from, month_till,
                                      logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    codes = {
        'water_for_hot_individual': 'ГВС теплоноситель индивидуальное',
        'heat_water_individual': 'ГВС подогрев индивидуальное',
        'water_individual': 'ХВС индивидуальное',
        'heat_individual': 'Отопление индивидуальное',
        'water_for_hot_public': 'ГВС теплоноситель ОДН',
        'heat_water_public': 'ГВС подогрев ОДН',
        'water_public': 'ХВС ОДН',
    }
    services = ServiceType.objects(
        __raw__={
            'code': {'$in': list(codes.keys())},
            'is_system': True,
        },
    ).only(
        'id',
        'code',
    ).as_pymongo()
    services = {s['_id']: codes[s['code']] for s in services}
    match_query = {
        'owner': provider_id,
        'month': {
            '$gte': month_from,
            '$lte': month_till,
        },
        'is_deleted': {'$ne': True},
        'doc.status': {'$in': CONDUCTED_STATUSES},
    }
    accruals = Accrual.objects(
        __raw__=match_query,
    ).aggregate(
        {
            '$unwind': '$services',
        },
        {
            '$match': {
                'services.service_type': {'$in': list(services.keys())},
            },
        },
        {
            '$group': {
                '_id': {
                    'account': '$account._id',
                    'month': '$month',
                    'service': '$services.service_type',
                },
                'value': {'$sum': '$services.value'},
                'recalc': {
                    '$sum': {
                        '$add': [
                            '$services.totals.recalculations',
                            '$services.totals.shortfalls',
                        ],
                    },
                },
                'priv': {'$sum': '$services.totals.privileges'},
                'cons': {'$sum': '$services.consumption'},
                'method': {'$first': '$services.method'},
                'tariff': {'$first': '$services.tariff'},
                'area_id': {'$first': '$account.area._id'},
                'house': {'$first': '$account.area.house._id'},
            },
        },
        {
            '$lookup': {
                'from': 'Account',
                'localField': '_id.account',
                'foreignField': '_id',
                'as': 'account',
            },
        },
        {
            '$unwind': '$account',
        },
        {
            '$lookup': {
                'from': 'Area',
                'localField': 'area_id',
                'foreignField': '_id',
                'as': 'area',
            },
        },
        {
            '$unwind': '$area',
        },
        {
            '$project': {
                'account': '$_id.account',
                'address': '$area.house.address',
                'area_num': '$area.str_number',
                'name': '$account.str_name',
                'month': '$_id.month',
                'service': '$_id.service',
                'method': 1,
                'tariff': 1,
                'cons': 1,
                'value': 1,
                'recalc': 1,
                'result': {'$add': ['$value', '$recalc']}
            },
        },
        {
            '$sort': {'account': 1},
        },
        {
            '$sort': {'month': 1},
        },
        allowDiskUse=True,
    )
    title_row = [
        'Адрес дома',
        '№ помещения',
        'ФИО ответственного',
        'период начисления ДД.ММ.ГГГГ',
        'Признак платежа',
        'Метод расчета(ИПУ/среднее/норматив)',
        'Тариф',
        'Расход',
        'Начислено',
        'перерасчет',
        'к оплате',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for accrual in accruals:
        row = [
            accrual['address'],
            accrual['area_num'],
            accrual['name'],
            accrual['month'].strftime('%d.%m.%Y'),
            services[accrual['service']],
            CONSUMPTION_TYPE_CHOICES_AS_DICT[accrual['method']],
            '{:.2f}'.format(accrual['tariff'] / 100),
            '{:.6f}'.format(accrual['cons']),
            '{:.2f}'.format(accrual['value'] / 100),
            '{:.2f}'.format(accrual['recalc'] / 100),
            '{:.2f}'.format(accrual['result'] / 100),
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result
