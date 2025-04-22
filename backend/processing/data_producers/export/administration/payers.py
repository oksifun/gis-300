import datetime

from dateutil.relativedelta import relativedelta

from app.auth.models.actors import Actor
from app.meters.models.meter import AreaMeter
from lib.dates import start_of_month, start_of_day
from processing.models.billing.accrual import Accrual
from app.house.models.house import House
from processing.models.billing.responsibility import Responsibility
from processing.models.billing.provider.main import Provider, BankProvider
from processing.models.billing.account import Tenant
from processing.models.billing.payment import Payment, PaymentDoc
from app.requests.models.request import Request
from app.tickets.models.tenants import Ticket
from processing.data_producers.associated.base import get_binded_houses
from processing.models.tasks.sber_autopay import SberAutoPayAccount
from utils.crm_utils import get_crm_client_ids


def get_acquiring_accrual_statistics(month, logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids(include_debtors=True)
    month = start_of_month(month)
    payers = Payment.objects(
        __raw__={
            'doc.provider': {'$in': clients_ids},
            'doc.date': {
                '$gte': month - relativedelta(years=1),
                '$lt': month + relativedelta(months=1),
            },
            'is_deleted': {'$ne': True},
            'by_card': True,
        },
    ).distinct(
        'account.id',
    )
    accrualed = Accrual.objects(
        __raw__={
            'account._id': {'$in': payers},
            'month': month,
        },
    ).distinct(
        'account._id',
    )
    tenants = Tenant.objects(
        pk__in=accrualed,
    ).only(
        'id',
        'number',
        'str_name',
        'area.str_number_full',
        'area.house.address',
    ).as_pymongo()
    title_row = [
        'Адрес',
        'ЛС',
        'ФИО',
        'Дата последней оплаты',
        'Количество оплат',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for tenant in tenants:
        pays = Payment.objects(
            account__id=tenant['_id'],
            is_deleted__ne=True,
            by_card=True,
        ).only(
            'doc.date',
        ).order_by(
            '-doc.date',
        ).as_pymongo()
        last_pay = list(pays[0: 1])
        if last_pay:
            last_pay = last_pay[0]['doc']['date'].strftime("%d.%m.%Y")
        else:
            last_pay = ''
        pay_count = pays.filter(
            doc__date__gte=month - relativedelta(years=1),
            doc__date__lt=month + relativedelta(months=1),
        ).count()
        row = [
            f"{tenant['area']['house']['address']}, "
            f"{tenant['area']['str_number_full']}",
            tenant['number'],
            tenant['str_name'],
            last_pay,
            str(pay_count)
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def get_acquiring_months_statistics(month, logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids(include_debtors=True)
    month = start_of_month(month)
    payers = Payment.objects(
        __raw__={
            'doc.provider': {'$in': clients_ids},
            'doc.date': {
                '$gte': month,
                '$lt': month + relativedelta(months=1),
            },
            'is_deleted': {'$ne': True},
            'by_card': True,
        },
    ).distinct(
        'account.id',
    )
    if logger:
        logger(f'плательщиков месяца: {len(payers)}')
    results = {p: 1 for p in payers}
    date = month - relativedelta(months=1)
    for ix in range(2, 13):
        payers = Payment.objects(
            __raw__={
                'account._id': {'$in': payers},
                'doc.date': {
                    '$gte': date,
                    '$lt': date + relativedelta(months=1),
                },
                'is_deleted': {'$ne': True},
                'by_card': True,
            },
        ).distinct(
            'account.id',
        )
        if logger:
            logger(f'плательщиков {ix} месяцев: {len(payers)}')
        for payer in payers:
            results[payer] += 1
        date -= relativedelta(months=1)
    stats = {}
    for payer, months in results.items():
        stats.setdefault(months, 0)
        stats[months] += 1
    stats = [(months, payers) for months, payers in stats.items()]
    title_row = [
        'Кол-во месяцев',
        'Кол-во жителей',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for data in sorted(stats, key=lambda i: i[0]):
        row = [
            str(data[0]),
            str(data[1]),
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


_ACQUIRING_DOC_TYPES = ['OtkrDoc', 'ElecsnetDoc']
_ACQUIRING_DOC_TYPES_LISTS = [['OtkrDoc'], ['ElecsnetDoc']]


def get_acquiring_payers_statistics(month_till, months=12, by_type=False,
                                    logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids(include_debtors=True)
    month = start_of_month(month_till)
    q = {
        'doc.provider': {'$in': clients_ids},
        'doc.date': {
            '$gte': month - relativedelta(months=months),
            '$lt': month + relativedelta(months=1),
        },
        'is_deleted': {'$ne': True},
        'sector_code': 'rent',
    }
    if by_type:
        q['doc._type'] = {'$in': _ACQUIRING_DOC_TYPES}
    else:
        q['by_card'] = True
    payers = Payment.objects(
        __raw__=q,
    ).distinct(
        'account.id',
    )
    if logger:
        logger(f'плательщиков за год: {len(payers)}')
    results = {
        p: ['' for ix in range(months)]
        for p in payers
    }
    date = month
    title_row = [
        'Адрес',
        'ЛС',
        'ФИО',
    ]
    for ix in range(months):
        q = {
            'account._id': {'$in': payers},
            'doc.date': {
                '$gte': date,
                '$lt': date + relativedelta(months=1),
            },
            'is_deleted': {'$ne': True},
            'sector_code': 'rent',
        }
        if by_type:
            q['doc._type'] = {'$in': _ACQUIRING_DOC_TYPES}
        else:
            q['by_card'] = True
        payers_stat = Payment.objects(
            __raw__=q,
        ).aggregate(
            {
                '$group': {
                    '_id': '$account._id',
                    'count': {'$sum': 1},
                },
            },
        )
        for payer in payers_stat:
            results[payer['_id']][ix] = str(payer['count'])
        title_row.append(f'Оплат в {date.strftime("%m.%Y")}')
        date -= relativedelta(months=1)
    if table_print:
        table_print(';'.join(title_row))
    tenants = Tenant.objects(
        pk__in=payers,
    ).only(
        'id',
        'area.str_number',
        'area.house.address',
        'number',
        'str_name',
    ).as_pymongo()
    table = [title_row]
    banks = {}
    for tenant in tenants:
        row = [
            f"{tenant['area']['house']['address']}, "
            f"{tenant['area']['str_number']}",
            tenant['number'],
            tenant['str_name'],
        ]
        tenant_results = results[tenant['_id']]
        if '' in tenant_results:
            months_list = [
                (month - relativedelta(months=ix), ix)
                for ix, val in enumerate(tenant_results)
                if val == ''
            ]
            q = {
                'account._id': tenant['_id'],
                'doc.date': {
                    '$gte': months_list[-1][0],
                    '$lt': months_list[0][0] + relativedelta(months=1),
                },
                'is_deleted': {'$ne': True},
                'sector_code': 'rent',
                'doc.bank': {'$ne': None},
            }
            if by_type:
                q['doc._type'] = {'$nin': _ACQUIRING_DOC_TYPES}
            else:
                q['by_card'] = {'$ne': True}
            payments = Payment.objects(
                __raw__=q,
            ).only(
                'doc.date',
                'doc.bank',
            ).as_pymongo()
            for payment in payments:
                for month_data in months_list:
                    if (
                            payment['doc']['date'] < month_data[0]
                            or payment['doc']['date']
                            >= month_data[0] + relativedelta(months=1)
                    ):
                        continue
                    if payment['doc']['bank'] not in banks:
                        bank = BankProvider.objects(
                            pk=payment['doc']['bank'],
                        ).only(
                            'bic_body',
                        ).as_pymongo().first()
                        if bank:
                            banks[payment['doc']['bank']] = \
                                bank['bic_body'][0]['NameP']
                        else:
                            banks[payment['doc']['bank']] = 'НЕИЗВЕСТНО'
                    if not tenant_results[month_data[1]]:
                        tenant_results[month_data[1]] = set()
                    tenant_results[month_data[1]].add(
                        banks[payment['doc']['bank']],
                    )
                    break
            for ix, tenant_data in enumerate(tenant_results):
                if isinstance(tenant_data, set):
                    tenant_results[ix] = ', '.join(tenant_data)
        row.extend(tenant_results)
        table.append(row)
        if table_print:
            table_print(';'.join(row))
    return table


def get_acquiring_providers_statistics(month_till, months=12, by_type=False,
                                       logger=None, table_print=None):
    """
    Сделано по задаче 345014
    """
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids(include_debtors=True)
    month = start_of_month(month_till)
    q = {
        'doc.provider': {'$in': clients_ids},
        'doc.date': {
            '$gte': month - relativedelta(months=months),
            '$lt': month + relativedelta(months=1),
        },
        'is_deleted': {'$ne': True},
    }
    if by_type:
        q['doc._type'] = {'$in': _ACQUIRING_DOC_TYPES}
    else:
        q['by_card'] = True
    payers = Payment.objects(
        __raw__=q,
    ).distinct(
        'doc.provider',
    )
    if logger:
        logger(f'плательщиков за год: {len(payers)}')
    results = {
        p: [None for ix in range(months)]
        for p in payers
    }
    date = month
    title_row = [
        'Организация',
        'ИНН',
        'Лиц.счетов всего',
    ]
    for ix in range(months):
        q = {
            'doc.provider': {'$in': payers},
            'doc.date': {
                '$gte': date,
                '$lt': date + relativedelta(months=1),
            },
            'is_deleted': {'$ne': True},
        }
        projection = {
            'provider': 1,
            'ack': {
                '$cond': [
                    {'$eq': ['$by_card', True]},
                    {'$literal': 1},
                    {'$literal': 0},
                ],
            },
        }
        if by_type:
            projection['ack']['$cond'][0] = {
                '$in': ['$doc_type', _ACQUIRING_DOC_TYPES],
            }
        payers_stat = Payment.objects(
            __raw__=q,
        ).aggregate(
            {
                '$project': {
                    'provider': '$doc.provider',
                    'doc_type': {'$arrayElemAt': ['$doc._type', 0]},
                    'by_card': 1,
                }
            },
            {
                '$project': projection,
            },
            {
                '$group': {
                    '_id': '$provider',
                    'ack': {'$sum': '$ack'},
                    'count': {'$sum': 1},
                },
            },
        )
        for payer in payers_stat:
            results[payer['_id']][ix] = [str(payer['count']), str(payer['ack'])]
            if payer['count'] == 0:
                results[payer['_id']][ix].append('0')
            else:
                results[payer['_id']][ix].append(
                    str(round(payer['ack'] / payer['count'] * 100, 2)),
                )
        title_row.append(
            f'кол-во платежей всего в {date.strftime("%m.%Y")}',
        )
        title_row.append(
            f'кол-во платежей через эквайринг в {date.strftime("%m.%Y")}',
        )
        title_row.append(
            f'% платежей через эквайринг в {date.strftime("%m.%Y")}',
        )
        date -= relativedelta(months=1)
    if table_print:
        table_print(';'.join(title_row))
    providers = Provider.objects(
        pk__in=payers,
    ).only(
        'id',
        'str_name',
        'inn',
    ).as_pymongo()
    table = [title_row]
    for provider in providers:
        resp = Responsibility.objects(
            __raw__={
                'provider': provider['_id'],
                '$and': [
                    {
                        '$or': [
                            {'date_from': None},
                            {'date_from': {'$lte': month_till}},
                        ],
                    },
                    {
                        '$or': [
                            {
                                'date_till': None,
                            },
                            {
                                'date_till': {
                                    '$gte': (
                                            month_till
                                            - relativedelta(months=12)
                                    ),
                                },
                            },
                        ],
                    },
                ],
            },
        ).distinct(
            'account._id',
        )
        row = [
            provider['str_name'],
            provider['inn'],
            str(len(resp)),
        ]
        tenant_results = results[provider['_id']]
        for res in tenant_results:
            if not res:
                row.extend(['', '', ''])
            else:
                row.extend(res)
        table.append(row)
        if table_print:
            table_print(';'.join(row))
    return table


def _get_house_responsibles(house_id, date_from, date_till):
    return Responsibility.objects(
        __raw__={
            'account.area.house._id': house_id,
            '$and': [
                {
                    '$or': [
                        {
                            'date_from': None,
                        },
                        {
                            'date_from': {
                                '$lt': date_till + relativedelta(days=1)
                            },
                        },
                    ],
                },
                {
                    '$or': [
                        {
                            'date_till': None,
                        },
                        {
                            'date_till': {
                                '$gte': date_from,
                            },
                        },
                    ],
                },
            ],
        },
    ).distinct(
        'account._id',
    )


def _get_house_cabinets_num(provider_id, house_id):
    return Actor.objects(
        __raw__={
            'provider._id': provider_id,
            'owner.house._id': house_id,
            'owner.owner_type': 'Tenant',
            'has_access': True,
        },
    ).count()


def get_acquiring_houses_statistics(date_till, months=6, by_type=False,
                                    logger=None, table_print=None):
    """
    Сделано по задаче 386187
    """
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids(include_debtors=True)
    title_row = [
        'Организация',
        'ИНН',
        'Адрес',
        '% оплаты через эквайринг',
        'Кол-во ЛС',
        'Кол-во кабинетов',
    ]
    date_till = start_of_day(date_till)
    date_from = date_till - relativedelta(months=months)
    q = {
        'doc.provider': {'$in': clients_ids},
        'doc.date': {
            '$gte': date_from,
            '$lt': date_till + relativedelta(days=1),
        },
        'is_deleted': {'$ne': True},
        'account': {'$ne': None},
    }
    projection = {
        'provider': 1,
        'house': 1,
        'ack': {
            '$cond': [
                {'$eq': ['$by_card', True]},
                {'$literal': 1},
                {'$literal': 0},
            ],
        },
    }
    if by_type:
        projection['ack']['$cond'][0] = {
            '$in': ['$doc_type', _ACQUIRING_DOC_TYPES],
        }
    payers_stat = Payment.objects(
        __raw__=q,
    ).aggregate(
        {
            '$project': {
                'provider': '$doc.provider',
                'house': '$account.area.house._id',
                'doc_type': {'$arrayElemAt': ['$doc._type', 0]},
                'by_card': 1,
            }
        },
        {
            '$project': projection,
        },
        {
            '$group': {
                '_id': {
                    'provider': '$provider',
                    'house': '$house',
                },
                'ack': {'$sum': '$ack'},
                'count': {'$sum': 1},
            },
        },
    )
    results = {}
    for payer in payers_stat:
        key = (payer['_id']['provider'], payer['_id']['house'])
        results[key] = [str(payer['count']), str(payer['ack'])]
        if payer['count'] == 0:
            results[key].append('0')
        else:
            results[key].append(
                str(round(payer['ack'] / payer['count'] * 100, 2)),
            )
    if table_print:
        table_print(';'.join(title_row))
    providers = Provider.objects(
        pk__in=clients_ids,
    ).only(
        'id',
        'str_name',
        'inn',
    ).as_pymongo()
    table = [title_row]
    for provider in providers:
        for house_id in get_binded_houses(provider['_id']):
            house = House.objects(
                pk=house_id,
            ).only(
                'address',
            ).as_pymongo().get()
            row = [
                provider['str_name'],
                provider['inn'],
                house['address'],
            ]
            house_results = results.get((provider['_id'], house_id))
            if not house_results:
                row.append('')
            else:
                row.append(house_results[2])
            resp = _get_house_responsibles(house_id, date_from, date_till)
            row.append(str(len(resp)))
            cabinets = _get_house_cabinets_num(provider['_id'], house_id)
            row.append(str(cabinets))
            table.append(row)
            if table_print:
                table_print(';'.join(row))
    return table


def get_payers_statistics(date_from, date_till, logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    providers = list(
        Provider.objects(
            __raw__={
                '_id': {'$in': clients_ids},
            },
        ).only(
            'id',
            'inn',
            'str_name',
        ).order_by(
            '-str_name',
        ).as_pymongo(),
    )
    title_row = [
        'Наименование',
        'ИНН',
        'Адрес',
        'Количество лицевых счетов',
        'Количество ЛКЖ',
        'Автоплательщиков Сбера',
        'Автоплательщиков других',
        'Подключивших наш автоплатеж',
        'из них автоплательщиков Сбера',

        'Количество активных ЛКЖ',
        'Количество плательщиков через ЛКЖ',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for provider in providers:
        for house_id in get_binded_houses(provider['_id']):
            house = House.objects(
                pk=house_id,
            ).only(
                'address',
            ).as_pymongo().get()
            tenants_has_access = Tenant.objects(
                __raw__={
                    'area.house._id': house_id,
                    'has_access': True,
                    'activation_code': {'$exists': False},
                    'activation_step': {'$exists': False},
                },
            ).only(
                'id',
                'area.id',
            ).as_pymongo()
            responsibles = Responsibility.objects(
                __raw__={
                    'account.area.house._id': house_id,
                },
            ).distinct(
                'account.id',
            )
            areas_tenants = {
                t['area']['_id']: t['_id']
                for t in tenants_has_access
            }
            areas_with_readings = AreaMeter.objects.aggregate(
                {
                    '$match': {
                        'area._id': {'$in': list(areas_tenants.keys())},
                    },
                },
                {
                    '$unwind': '$readings',
                },
                {
                    '$match': {
                        'readings.created_at': {
                            '$gte': date_from,
                            '$lt': date_till,
                        },
                        'readings.created_by': 'tenant',
                    },
                },
                {
                    '$group': {'_id': '$area._id'},
                },
            )
            tenants_with_readings = [
                areas_tenants[a['_id']]
                for a in areas_with_readings
            ]
            tenants_has_access = list({t['_id'] for t in tenants_has_access})
            tenants_with_requests = Request.objects(
                __raw__={
                    'tenant._id': {'$in': tenants_has_access},
                },
            ).distinct(
                'tenant.id',
            )
            tenants_with_tickets = Ticket.objects(
                __raw__={
                    'initial.author': {'$in': tenants_has_access},
                },
            ).distinct(
                'initial.author',
            )
            tenants_with_payments = Payment.objects(
                __raw__={
                    'account._id': {'$in': tenants_has_access},
                    'doc.date': {'$gte': date_from, '$lt': date_till},
                    'is_deleted': {'$ne': True},
                    # TODO: вернуть, когда открытие исправит transaction_info
                    'doc._type': 'OtkrDoc',
                    #'by_card': True,
                },
            ).distinct(
                'account.id',
            )
            tenants_with_activity = list(
                set(tenants_with_readings)
                | set(tenants_with_requests)
                | set(tenants_with_tickets)
                | set(tenants_with_payments)
            )
            tenants_want_autopay = Tenant.objects(
                __raw__={
                    'area.house._id': house_id,
                    'settings.sber_auto_pay.state': 'accepted',
                },
            ).distinct(
                'id',
            )
            tenants_with_sber_autopay = get_tenants_with_sber_autopay(
                date_from,
                date_till,
                house_id=house_id,
            )
            tenants_with_other_autopay = Payment.objects.aggregate(
                {
                    '$match': {
                        'account.area.house._id': house_id,
                        'doc._type': {'$ne': 'SberDoc'},
                        'date': {'$gte': date_from, '$lt': date_till},
                        'is_deleted': {'$ne': True},
                    },
                },
                {
                    '$project': {
                        'account': '$account._id',
                        'sector': '$sector_code',
                        'value': 1,
                        'day': {'$dayOfMonth': '$date'},
                        'month': {'$month': '$date'},
                        'provider': '$doc.provider',
                        'type': {'$arrayElemAt': ['$_type', 0]},
                    },
                },
                {
                    '$group': {
                        '_id': {
                            'account': '$account',
                            'sector': '$sector',
                            'day': '$day',
                            'value': '$value',
                            'type': '$type',
                        },
                        'months': {'$addToSet': '$month'},
                        'value': {'$sum': '$value'},
                        'provider': {'$first': '$provider'},
                    },
                },
                {
                    '$match': {
                        'months': {'$size': 3},
                    },
                },
                {
                    '$group': {
                        '_id': '$_id.account',
                    },
                },
                allowDiskUse=True,
            )
            tenants_with_other_autopay = [
                t['_id'] for t in tenants_with_other_autopay
            ]
            row = [
                provider.get('inn') or '',
                provider['str_name'],
                house['address'],

                str(len(responsibles)),
                str(len(tenants_has_access)),
                str(len(tenants_with_sber_autopay)),
                str(len(tenants_with_other_autopay)),
                str(len(tenants_want_autopay)),
                str(
                    len(
                        set(tenants_want_autopay)
                        & set(tenants_with_sber_autopay)
                    ),
                ),

                str(len(tenants_with_activity)),
                str(len(tenants_with_payments)),
            ]
            result.append(row)
            if table_print:
                table_print(';'.join(row))
    return result


def get_tenants_with_sber_autopay(date_from, date_till,
                                  house_id=None, with_provider=False):
    match_query = {
        'doc._type': 'SberDoc',
        'date': {'$gte': date_from, '$lt': date_till},
        'is_deleted': {'$ne': True},
    }
    if house_id:
        match_query['account.area.house._id'] = house_id
    tenants_with_sber_autopay = Payment.objects.aggregate(
        {
            '$match': match_query,
        },
        {
            '$project': {
                'account': '$account._id',
                'sector': '$sector_code',
                'value': 1,
                'day': {'$dayOfMonth': '$date'},
                'month': {'$month': '$date'},
                'provider': '$doc.provider',
            },
        },
        {
            '$group': {
                '_id': {
                    'account': '$account',
                    'sector': '$sector',
                    'day': '$day',
                },
                'months': {'$addToSet': '$month'},
                'value': {'$sum': '$value'},
                'provider': {'$first': '$provider'},
            },
        },
        {
            '$match': {
                'months': {'$size': 3},
            },
        },
        {
            '$group': {
                '_id': '$_id.account',
                'provider': {'$first': '$provider'},
            },
        },
        allowDiskUse=True,
    )
    if with_provider:
        return [(t['_id'], t['provider']) for t in tenants_with_sber_autopay]
    return [t['_id'] for t in tenants_with_sber_autopay]


def get_sber_autopayers_phones(date_from, date_till,
                               logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    title_row = [
        'Название организации',
        'Адрес жителя',
        'ФИО жителя',
        'Телефон жителя',
        'E - mail жителя',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    tenants = get_tenants_with_sber_autopay(date_from, date_till)
    payers = Payment.objects(
        account__id__in=tenants,
        doc__provider__in=clients_ids,
        doc__date__gte=date_from,
        doc__date__lt=date_till + relativedelta(days=1),
    ).aggregate(
        {
            '$group': {
                '_id': '$account._id',
                'provider': {'$first': '$doc.provider'},
            },
        },
    )
    payers = {p['_id']: p['provider'] for p in payers}
    tenants = Tenant.objects(
        pk__in=list(payers.keys()),
    ).only(
        'id',
        'phones',
        'email',
        'str_name',
        'area',
    ).as_pymongo()
    providers = Provider.objects(
        pk__in=list(set(payers.values())),
    ).only(
        'id',
        'inn',
        'str_name',
    ).as_pymongo()
    providers = {p['_id']: p for p in providers}
    for tenant in tenants:
        for phone in tenant.get('phones') or []:
            row = [
                providers[payers[tenant['_id']]]['str_name'],
                '{}, {}'.format(
                    tenant['area']['house']['address'],
                    tenant['area']['str_number_full'],
                ),
                tenant['str_name'],
                '{}{}'.format(
                    phone.get('code') or '',
                    phone.get('number') or '',
                ),
                tenant.get('email') or '',
            ]
            result.append(row)
            if table_print:
                table_print(';'.join(row))
    return result


def get_autopayers_count():
    autopayers = Tenant.objects(
        p_settings__auto=True,
        p_settings__recurrent=True,
    ).distinct(
        'id',
    )
    print('автоплательщиков', len(autopayers))
    tenants = SberAutoPayAccount.objects(
        account__in=autopayers,
    ).distinct(
        'account',
    )
    print('из них сберовских', len(tenants))


def get_payers_by_doc_type(doc_types, date_from, date_till,
                           include_cabinet_payers=True,
                           logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    providers = list(
        Provider.objects(
            __raw__={
                '_id': {'$in': clients_ids},
            },
        ).only(
            'id',
            'inn',
            'str_name',
        ).order_by(
            '-str_name',
        ).as_pymongo(),
    )
    title_row = [
        'Лицевой счёт',
        'ФИО',
        'Адрес',
        'Квартира',
        'Организация',
        'ИНН',
        'Есть email',
        'Email',
        'Есть телефон',
        'Телефон',
        'Есть ЛКЖ',
        'Есть telegram-бот',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for provider in providers:
        for house_id in get_binded_houses(provider['_id']):
            house = House.objects(
                pk=house_id,
            ).only(
                'address',
            ).as_pymongo().get()
            match_query = {
                'doc.provider': provider['_id'],
                'account.area.house._id': house_id,
                'doc.date': {'$gte': date_from, '$lt': date_till},
                'is_deleted': {'$ne': True},
                'doc._type': {'$in': doc_types},
            }
            if not include_cabinet_payers:
                match_query['by_card'] = {'$ne': True}
            tenants_with_payments = Payment.objects(
                __raw__=match_query,
            ).distinct(
                'account.id',
            )
            tenants = Tenant.objects(
                __raw__={
                    '_id': {'$in': tenants_with_payments},
                },
            ).only(
                'id',
                'number',
                'area.str_number',
                'str_name',
                'phones',
                'email',
                'telegram_chats',
            ).order_by(
                'area.order',
            ).as_pymongo()
            for tenant in tenants:
                actor = Actor.objects(
                    owner__id=tenant['_id'],
                    has_access=True,
                ).only(
                    'id',
                    'has_access',
                ).first()
                phones = ', '.join(
                    [
                        f'{p.get("code") or ""}{p.get("number") or ""}'
                        for p in tenant.get('phones') or []
                    ],
                )
                row = [
                    tenant['number'],
                    tenant['str_name'],
                    house['address'],
                    tenant['area']['str_number'],
                    provider['str_name'],
                    provider.get('inn') or '',
                    'да' if tenant.get('email') else 'нет',
                    tenant.get('email') or '',
                    'да' if phones else 'нет',
                    phones,
                    'да' if actor else 'нет',
                    'да' if tenant.get('telegram_chats') else 'нет',
                ]
                result.append(row)
                if table_print:
                    table_print(';'.join(row))
    return result


def get_payers_by_cabinet(date_from, date_till,
                          logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    providers = list(
        Provider.objects(
            __raw__={
                '_id': {'$in': clients_ids},
            },
        ).only(
            'id',
            'inn',
            'str_name',
        ).order_by(
            '-str_name',
        ).as_pymongo(),
    )
    title_row = [
        'Организация',
        'ИНН',
        'Адрес',
        'Квартира',
        'Лицевой счёт',
        'ФИО',
        'Телефон',
        'Email',
        'Платежей через ЛКЖ',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for provider in providers:
        for house_id in get_binded_houses(provider['_id']):
            house = House.objects(
                pk=house_id,
            ).only(
                'address',
            ).as_pymongo().get()
            match_query = {
                'doc.provider': provider['_id'],
                'account.area.house._id': house_id,
                'doc.date': {'$gte': date_from, '$lt': date_till},
                'is_deleted': {'$ne': True},
                'by_card': True,
            }
            tenants_with_payments = Payment.objects(
                __raw__=match_query,
            ).aggregate(
                {
                    '$group': {
                        '_id': '$account._id',
                        'count': {'$sum': 1},
                    },
                },
            )
            tenants_with_payments = {
                t['_id']: t['count']
                for t in tenants_with_payments
            }
            tenants = Tenant.objects(
                __raw__={
                    '_id': {'$in': list(tenants_with_payments.keys())},
                },
            ).only(
                'id',
                'number',
                'area.str_number',
                'str_name',
                'phones',
                'email',
                'has_access',
                'activation_code',
                'activation_step',
            ).order_by(
                'area.order',
            ).as_pymongo()
            for tenant in tenants:
                row = [
                    provider['str_name'],
                    provider.get('inn') or '',
                    house['address'],
                    tenant['area']['str_number'],
                    tenant['number'],
                    tenant['str_name'],
                    ', '.join(
                        [
                            f'{p.get("code") or ""}{p.get("number") or ""}'
                            for p in tenant.get('phones') or []
                        ],
                    ),
                    tenant.get('email') or '',
                    str(tenants_with_payments[tenant['_id']]),
                ]
                result.append(row)
                if table_print:
                    table_print(';'.join(row))
    return result


def get_pes_payers(date_from, date_till, logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    title_row = [
        'Организация',
        'id',
        'Сумма платежей',
        'Сумма ПЭС',
        '% ПЭС',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    payments = PaymentDoc.objects(
        provider__in=clients_ids,
        date__gte=date_from,
        date__lt=date_till + relativedelta(days=1),
        is_deleted__ne=True,
    ).aggregate(
        {
            '$project': {
                'provider': 1,
                '_type': {'$arrayElemAt': ['$_type', 0]},
                'value': '$totals.value',
            },
        },
        {
            '$project': {
                'provider': 1,
                'value': 1,
                'pes': {
                    '$cond': [
                        {'$in': ['$_type', ['PesAltDoc', 'PesDoc']]},
                        {'$literal': 1},
                        {'$literal': 0},
                    ],
                },
            },
        },
        {
            '$group': {
                '_id': {
                    'provider': '$provider',
                    'pes': '$pes',
                },
                'value': {'$sum': '$value'},
            },
        },
        {
            '$project': {
                '_id': 1,
                'pes': {
                    '$cond': [
                        {'$eq': ['$_id.pes', 1]},
                        '$value',
                        {'$literal': 0},
                    ],
                },
                'not_pes': {
                    '$cond': [
                        {'$eq': ['$_id.pes', 1]},
                        {'$literal': 0},
                        '$value',
                    ],
                },
            },
        },
        {
            '$group': {
                '_id': '$_id.provider',
                'pes': {'$sum': '$pes'},
                'not_pes': {'$sum': '$not_pes'},
            },
        },
        {
            '$lookup': {
                'from': 'Provider',
                'localField': '_id',
                'foreignField': '_id',
                'as': 'provider',
            },
        },
        {
            '$unwind': '$provider',
        },
        {
            '$project': {
                '_id': 1,
                'name': '$provider.str_name',
                'pes': 1,
                'not_pes': 1,
            },
        },
        {
            '$sort': {'name': 1},
        },
    )
    for payment in payments:
        total = payment['pes'] + payment['not_pes']
        row = [
            payment['name'],
            str(payment['_id']),
            str(total / 100),
            str(payment['pes'] / 100),
            str(payment['pes'] / (total or 1) * 100),
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def get_pes_stats(date_from, date_till, logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    title_row = [
        'Организация',
        'ИНН',
        'Количество ЛС',
        'Количество платежей в ПЭС',
        'Сумма платежей в ПЭС',
        'На реестрах сбера',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    payments = PaymentDoc.objects(
        provider__in=clients_ids,
        date__gte=date_from,
        date__lt=date_till + relativedelta(days=1),
        is_deleted__ne=True,
    ).aggregate(
        {
            '$project': {
                'provider': 1,
                '_type': {'$arrayElemAt': ['$_type', 0]},
                'value': '$totals.value',
            },
        },
        {
            '$project': {
                'provider': 1,
                'pes_v': {
                    '$cond': [
                        {'$in': ['$_type', ['PesAltDoc', 'PesDoc']]},
                        '$value',
                        {'$literal': 0},
                    ],
                },
                'pes_c': {
                    '$cond': [
                        {'$in': ['$_type', ['PesAltDoc', 'PesDoc']]},
                        {'$literal': 1},
                        {'$literal': 0},
                    ],
                },
                'sber': {
                    '$cond': [
                        {'$eq': ['$_type', 'SberDoc']},
                        {'$literal': 1},
                        {'$literal': 0},
                    ],
                },
            },
        },
        {
            '$group': {
                '_id': '$provider',
                'value': {'$sum': '$pes_v'},
                'number': {'$sum': '$pes_c'},
                'sber': {'$max': '$sber'},
            },
        },
        {
            '$lookup': {
                'from': 'Provider',
                'localField': '_id',
                'foreignField': '_id',
                'as': 'provider',
            },
        },
        {
            '$unwind': '$provider',
        },
        {
            '$project': {
                '_id': 1,
                'name': '$provider.str_name',
                'inn': '$provider.inn',
                'value': 1,
                'number': 1,
                'sber': 1,
            },
        },
        {
            '$sort': {'name': 1},
        },
    )
    for payment in payments:
        resp = Responsibility.objects(
            __raw__={
                'provider': payment['_id'],
                '$and': [
                    {
                        '$or': [
                            {'date_from': None},
                            {'date_from': {'$lte': date_till}},
                        ],
                    },
                    {
                        '$or': [
                            {'date_till': None},
                            {'date_till': {'$gte': date_from}},
                        ],
                    },
                ],
            },
        ).distinct(
            'account._id',
        )
        row = [
            payment['name'],
            payment['inn'],
            str(len(resp)),
            str(payment['number']),
            str(payment['value'] / 100),
            'да' if payment['sber'] else 'нет',
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def get_paydoc_stats(date_from, date_till, logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    title_row = [
        'Наименование',
        'ИНН',
        'Сумма платежей всего',
        'Средняя сумма платежа',
        'в т. ч. сумма платежей в реестрах Сбербанка',
        'в т. ч. сумма платежей в реестрах ПЭС',
        'в т.ч. сумма платежей в реестрах Почта России',
        'в т. ч. сумма платежей в реестрах ErtsopDoc',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    payments = PaymentDoc.objects(
        provider__in=clients_ids,
        date__gte=date_from,
        date__lt=date_till + relativedelta(days=1),
        is_deleted__ne=True,
    ).aggregate(
        {
            '$project': {
                'provider': 1,
                '_type': {'$arrayElemAt': ['$_type', 0]},
                'value': '$totals.value',
                'count': '$totals.count',
            },
        },
        {
            '$project': {
                'provider': 1,
                'value': 1,
                'count': 1,
                'pes': {
                    '$cond': [
                        {'$in': ['$_type', ['PesAltDoc', 'PesDoc']]},
                        '$value',
                        {'$literal': 0},
                    ],
                },
                'sber': {
                    '$cond': [
                        {'$eq': ['$_type', 'SberDoc']},
                        '$value',
                        {'$literal': 0},
                    ],
                },
                'pochta': {
                    '$cond': [
                        {'$eq': ['$_type', 'PostDoc']},
                        '$value',
                        {'$literal': 0},
                    ],
                },
                'ertsop': {
                    '$cond': [
                        {'$eq': ['$_type', 'ErtsopDoc']},
                        '$value',
                        {'$literal': 0},
                    ],
                },
            },
        },
        {
            '$group': {
                '_id': '$provider',
                'value': {'$sum': '$value'},
                'count': {'$sum': '$count'},
                'pes': {'$sum': '$pes'},
                'sber': {'$sum': '$sber'},
                'pochta': {'$sum': '$pochta'},
                'ertsop': {'$sum': '$ertsop'},
            },
        },
        {
            '$lookup': {
                'from': 'Provider',
                'localField': '_id',
                'foreignField': '_id',
                'as': 'provider',
            },
        },
        {
            '$unwind': '$provider',
        },
        {
            '$project': {
                '_id': 1,
                'name': '$provider.str_name',
                'inn': '$provider.inn',
                'value': 1,
                'count': 1,
                'pes': 1,
                'sber': 1,
                'pochta': 1,
                'ertsop': 1,
            },
        },
        {
            '$sort': {'name': 1},
        },
    )
    for payment in payments:
        row = [
            payment['name'],
            payment.get('inn') or '',
            str(payment['value'] / 100),
            str(payment['value'] / payment['count'] / 100),
            str(payment['sber'] / 100),
            str(payment['pes'] / 100),
            str(payment['pochta'] / 100),
            str(payment['ertsop'] / 100),
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def get_tenants_pay_stats(date_from, date_till, logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    title_row = [
        'Наименование',
        'ИНН',
        'Сумма платежей всего',
        'Средняя сумма платежа',
        'Ответственных всего',
        'Ответственных с контактами (телефон или e-mail)',
        'Ответственных с ЛКЖ',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    payments = PaymentDoc.objects(
        provider__in=clients_ids,
        date__gte=date_from,
        date__lt=date_till + relativedelta(days=1),
        is_deleted__ne=True,
    ).aggregate(
        {
            '$project': {
                'provider': 1,
                '_type': {'$arrayElemAt': ['$_type', 0]},
                'value': '$totals.value',
                'count': '$totals.count',
            },
        },
        {
            '$group': {
                '_id': '$provider',
                'value': {'$sum': '$value'},
                'count': {'$sum': '$count'},
            },
        },
        {
            '$lookup': {
                'from': 'Provider',
                'localField': '_id',
                'foreignField': '_id',
                'as': 'provider',
            },
        },
        {
            '$unwind': '$provider',
        },
        {
            '$project': {
                '_id': 1,
                'name': '$provider.str_name',
                'inn': '$provider.inn',
                'value': 1,
                'count': 1,
            },
        },
        {
            '$sort': {'name': 1},
        },
    )
    date = datetime.datetime.now()
    for payment in payments:
        resp = _get_responsibles(payment['_id'], date)
        with_contacts = Tenant.objects(
            __raw__={
                '_id': {'$in': resp},
                '$or': [
                    {'phones.0': {'$exists': True}},
                    {'email': {'$ne': None}},
                ],
            }
        ).count()
        with_cabinet = Tenant.objects(
            __raw__={
                '_id': {'$in': resp},
                'has_access': True,
                'activation_code': None,
                'activation_step': None,
            }
        ).count()
        row = [
            payment['name'],
            payment.get('inn') or '',
            str(payment['value'] / 100),
            str(payment['value'] / payment['count'] / 100),
            str(with_contacts),
            str(with_cabinet),
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def _get_responsibles(provider_id, date, custom_query=None):
    query = {
        'provider': provider_id,
        '$and': [
            {
                '$or': [
                    {'date_from': None},
                    {'date_from': {'$lte': date}},
                ],
            },
            {
                '$or': [
                    {'date_till': None},
                    {'date_till': {'$gte': date}},
                ],
            },
        ],
    }
    if custom_query:
        query.update(custom_query)
    return Responsibility.objects(__raw__=query).distinct('account.id')


def get_payers_by_banks(banks_ids, date_from, date_till,
                        logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    payers = list(
        Payment.objects(
            __raw__={
                'doc.provider': {
                    '$in': clients_ids,
                },
                'doc.date': {
                    '$gte': date_from,
                    '$lt': date_till + relativedelta(days=1),
                },
                'doc.bank': {
                    '$in': banks_ids,
                },
            },
        ).aggregate(
            {
                '$group': {
                    '_id': '$account._id',
                    'banks': {'$addToSet': '$doc.bank'},
                    'provider': {'$first': '$doc.provider'},
                },
            },
        ),
    )
    title_row = [
        'Наименование банка',
        'Номер лицевого счета',
        'Есть личный кабинет?',
        'Есть оплата через эквайринг?',
        'Дата последней оплаты через эквайринг',
        'Есть телефон?',
        'Есть email?',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    banks = {p.id: p for p in BankProvider.objects(pk__in=banks_ids).all()}
    for payer in payers:
        if not payer.get('_id'):
            continue
        tenant = Tenant.objects(
            pk=payer['_id'],
        ).only(
            'id',
            'number',
            'phones',
            'email',
        ).as_pymongo().first()
        if not tenant:
            continue
        actor = Actor.objects(
            owner__id=tenant['_id'],
            has_access=True,
        ).only(
            'id',
            'has_access',
        ).first()
        phones = ', '.join(
            [
                f'{p.get("code") or ""}{p.get("number") or ""}'
                for p in tenant.get('phones') or []
            ],
        )
        ack_pay = Payment.objects(
            __raw__={
                'account._id': tenant['_id'],
                'by_card': True,
                'doc.date': {
                    '$gte': date_from,
                    '$lt': date_till + relativedelta(days=1),
                },
            },
        ).only(
            'date',
        ).as_pymongo().first()
        row = [
            banks[payer['banks'][0]].bic_body[0].NameP,
            tenant['number'],
            'да' if actor else 'нет',
            'да' if ack_pay else 'нет',
            ack_pay['date'].strftime("%d.%m.%Y") if ack_pay else '',
            'да' if phones else 'нет',
            'да' if tenant.get('email') else 'нет',
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result
