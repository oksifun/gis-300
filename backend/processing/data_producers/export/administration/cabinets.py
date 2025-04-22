import datetime

from dateutil.relativedelta import relativedelta

from app.area.models.area import Area
from lib.dates import start_of_month
from processing.data_producers.associated.base import get_binded_houses
from processing.models.billing.account import Tenant
from processing.models.billing.provider.main import Provider
from processing.models.billing.responsibility import Responsibility
from utils.crm_utils import get_crm_client_ids


def get_cabinets_count_stats(dates, logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    title_row = [
        'ИНН',
        'Наименование организации',
    ]
    for date in dates:
        title_row.extend(
            [
                f'Кол-во ответственных ({date.strftime("%d.%m.%Y")})',
                f'Кол-во ЛКЖ ({date.strftime("%d.%m.%Y")})',
                f'В т.ч. за посл. 7 дн. ({date.strftime("%d.%m.%Y")})',
            ],
        )
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    dates_week = [
        (
            date.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            - relativedelta(days=7)
        )
        for date in dates
    ]
    for provider_id in clients_ids:
        provider = Provider.objects(
            pk=provider_id,
        ).only(
            'id',
            'str_name',
            'inn',
        ).as_pymongo().first()
        if not provider:
            continue
        houses = get_binded_houses(provider_id)
        row = [
            provider.get('inn') or '',
            provider['str_name'],
        ]
        for ix, date in enumerate(dates):
            query = {
                'has_access': True,
                'activation_code': {'$exists': False},
                'activation_step': {'$exists': False},
                'area.house._id': {'$in': houses},
                'get_access_date': {'$lt': date},
            }
            users_count = Tenant.objects(__raw__=query).count()
            query['get_access_date']['$gte'] = dates_week[ix]
            new_users_count = Tenant.objects(__raw__=query).count()
            responsibles_count = len(
                Responsibility.objects(
                    __raw__={
                        'provider': provider_id,
                        'account.area.house._id': {
                            '$in': houses,
                        },
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
                    },
                ).distinct(
                    'account.id',
                ),
            )
            row.extend(
                [
                    str(responsibles_count),
                    str(users_count),
                    str(new_users_count),
                ],
            )
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def get_cabinets_count_stats_monthly(dates, show_squares=False, logger=None,
                                     table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    title_row = [
        'ИНН',
        'Наименование организации',
    ]
    for date in dates:
        title_row.append(f'Выдано ЛКЖ в {date.strftime("%m.%Y")}')
        if show_squares:
            title_row.append(f'Площадь ЛКЖ в {date.strftime("%m.%Y")}')
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for provider_id in clients_ids:
        provider = Provider.objects(
            pk=provider_id,
        ).only(
            'id',
            'str_name',
            'inn',
        ).as_pymongo().first()
        if not provider:
            continue
        houses = get_binded_houses(provider_id)
        row = [
            provider.get('inn') or '',
            provider['str_name'],
        ]
        for ix, date in enumerate(dates):
            query = {
                'has_access': True,
                'activation_code': {'$exists': False},
                'activation_step': {'$exists': False},
                'area.house._id': {'$in': houses},
                'get_access_date': {
                    '$gte': start_of_month(date),
                    '$lt': start_of_month(date) + relativedelta(months=1),
                },
            }
            queryset = Tenant.objects(__raw__=query)
            row.append(str(queryset.count()))
            if show_squares:
                areas = queryset.distinct('area.id')
                squares = Area.objects(
                    pk__in=areas,
                ).only(
                    'area_total',
                ).as_pymongo()
                row.append(str(sum(s['area_total'] for s in squares)))
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def get_cabinets_count_stats_by_months(months_count, show_squares=False,
                                       logger=None, table_print=None):
    dates = []
    date = start_of_month(datetime.datetime.now())
    for i in range(months_count):
        dates.append(date)
        date -= relativedelta(months=1)
    return get_cabinets_count_stats_monthly(
        dates,
        show_squares=show_squares,
        logger=logger,
        table_print=table_print,
    )

