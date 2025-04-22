import datetime

from dateutil.relativedelta import relativedelta

from processing.data_producers.balance.base import CONDUCTED_STATUSES
from processing.models.billing.account import Tenant
from processing.models.billing.accrual import Accrual
from processing.models.billing.payment import Payment


def get_acquiring_by_months_count(year_from, year_till, logger=None,
                                  table_print=None):
    if logger:
        logger('Получение исходных данных')
    title_row = [
        'Месяц',
    ]
    for ix in range(1, 12):
        title_row.append(f'{ix} платежей в год (шт)')
        title_row.append(f'{ix} платежей в год (руб)')
    title_row.append('12+ платежей в год (шт)')
    title_row.append('12+ платежей в год (руб)')
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    year = year_from
    while year <= year_till:
        pay = Payment.objects(
            __raw__={
                'doc.date': {
                    '$gte': datetime.datetime(year, 1, 1),
                    '$lt': datetime.datetime(year + 1, 1, 1),
                },
                'is_deleted': {'$ne': True},
                'by_card': True,
                'sector_code': 'rent',
            },
        ).aggregate(
            {
                '$group': {
                    '_id': '$account._id',
                    'value': {'$sum': '$value'},
                    'count': {'$sum': 1},
                },
            },
            {
                '$group': {
                    '_id': '$count',
                    'sum': {'$sum': '$value'},
                    'count': {'$sum': 1},
                },
            }
        )
        pay = list(pay)
        if pay:
            pay = {p['_id']: p for p in pay}
        else:
            pay = {}
        row = [
            str(year),
        ]
        for ix in range(1, 12):
            if ix in pay:
                row.append(str(pay[ix]['count']))
                row.append(str(pay[ix]['sum'] / 100))
            else:
                row.append("0")
                row.append("0")
        count_12 = sum(v['count'] for k, v in pay.items() if k >= 12)
        sum_12 = sum(v['count'] for k, v in pay.items() if k >= 12)
        row.append(str(count_12))
        row.append(str(sum_12 / 100))
        result.append(row)
        if table_print:
            table_print(';'.join(row))
        year += 1
    return result


def get_autopays_monthly(month_from, month_till, logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    title_row = [
        'Месяц',
        'Кол-во автоплатежей',
        'Сумма автоплатежей',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    month = month_from
    while month <= month_till:
        pay = Payment.objects(
            __raw__={
                'doc.date': {
                    '$gte': month,
                    '$lt': month + relativedelta(months=1),
                },
                'is_deleted': {'$ne': True},
                'auto_payment': True,
            },
        ).aggregate(
            {
                '$group': {
                    '_id': '',
                    'sum': {'$sum': '$value'},
                    'count': {'$sum': 1},
                },
            },
        )
        pay = list(pay)
        pay = pay[0] if pay else {'sum': 0, 'count': 0}
        row = [
            month.strftime('%m.%Y'),
            str(pay['count']),
            str(pay['sum'] / 100),
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
        month += relativedelta(months=1)
    return result


def get_accruals_payments_monthly(month_from, month_till, logger=None,
                                  table_print=None):
    if logger:
        logger('Получение исходных данных')
    title_row = [
        'Месяц',
        'Начислено',
        'Оплачено',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    month = month_from
    while month <= month_till:
        accrual = Accrual.objects(
            __raw__={
                'doc.date': {
                    '$gte': month,
                    '$lt': month + relativedelta(months=1),
                },
                'doc.status': {'$in': CONDUCTED_STATUSES},
                'is_deleted': {'$ne': True},
            },
        ).aggregate(
            {
                '$group': {
                    '_id': '',
                    'sum': {'$sum': '$value'},
                },
            },
        )
        accrual = list(accrual)
        accrual = accrual[0]['sum'] if accrual else 0
        pay = Payment.objects(
            __raw__={
                'doc.date': {
                    '$gte': month,
                    '$lt': month + relativedelta(months=1),
                },
                'is_deleted': {'$ne': True},
            },
        ).aggregate(
            {
                '$group': {
                    '_id': '',
                    'sum': {'$sum': '$value'},
                },
            },
        )
        pay = list(pay)
        pay = pay[0]['sum'] if pay else 0
        row = [
            month.strftime('%m.%Y'),
            str(accrual / 100),
            str(pay / 100),
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
        month += relativedelta(months=1)
    return result


def get_cabinets_pay_monthly(month_from, month_till, logger=None,
                             table_print=None):
    if logger:
        logger('Получение исходных данных')
    title_row = [
        'Месяц',
        'Сумма платежей жителями с ЛКЖ',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    month = month_from
    while month <= month_till:
        tenants = Tenant.objects(
            __raw__={
                '_type': 'Tenant',
                'get_access_date': {'$lt': month + relativedelta(months=1)},
            },
        ).distinct(
            'id',
        )
        if not tenants:
            logger('ПУСТО' + month.strftime('%m.%Y'))
            month += relativedelta(months=1)
            continue
        pay = Payment.objects(
            __raw__={
                'account._id': {'$in': tenants},
                'doc.date': {
                    '$gte': month,
                    '$lt': month + relativedelta(months=1),
                },
                'is_deleted': {'$ne': True},
            },
        ).aggregate(
            {
                '$group': {
                    '_id': '',
                    'sum': {'$sum': '$value'},
                },
            },
        )
        pay = list(pay)
        pay = pay[0] if pay else {'sum': 0}
        row = [
            month.strftime('%m.%Y'),
            str(pay['sum'] / 100),
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
        month += relativedelta(months=1)
    return result
