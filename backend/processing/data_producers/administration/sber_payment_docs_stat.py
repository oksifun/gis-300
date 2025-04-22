from datetime import datetime

from dateutil.relativedelta import relativedelta
from processing.models.billing.payment import Payment
from utils.crm_utils import get_crm_client_ids


def get_sber_payers(date_from, date_till):
    print('Получение исходных данных')
    clients_ids = get_crm_client_ids(include_debtors=True)
    title_row = [
        'Организация',
        'ИНН',
        '% Сбербанк',
    ]
    print(';'.join(title_row))
    payments = Payment.objects(
        doc__provider__in=clients_ids,
        doc__date__gte=date_from,
        doc__date__lt=date_till + relativedelta(days=1),
        is_deleted__ne=True,
    ).aggregate(
        {
            '$project': {
                'provider': '$doc.provider',
                '_type': {'$arrayElemAt': ['$doc._type', 0]},
            },
        },
        {
            '$project': {
                'provider': 1,
                'sber': {
                    '$cond': [
                        {'$in': ['$_type', ['SberDoc']]},
                        {'$literal': 1},
                        {'$literal': 0},
                    ],
                },
            },
        },
        {
            '$project': {
                'provider': 1,
                'sber': {
                    '$cond': [
                        {'$eq': ['$sber', 1]},
                        {'$literal': 1},
                        {'$literal': 0},
                    ],
                },
                'not_sber': {
                    '$cond': [
                        {'$eq': ['$sber', 1]},
                        {'$literal': 0},
                        {'$literal': 1},
                    ],
                },
            },
        },
        {
            '$group': {
                '_id': '$provider',
                'sber': {'$sum': '$sber'},
                'not_sber': {'$sum': '$not_sber'},
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
                'sber': 1,
                'not_sber': 1,
            },
        },
        {
            '$sort': {'name': 1},
        },
    )
    if payments:
        for payment in payments:
            total = payment['sber'] + payment['not_sber']
            row = [
                payment['name'],
                payment.get('inn') or '',
                str(round(payment['sber'] / (total or 1) * 100, 2)),
            ]
            print(';'.join(row))
    else:
        print('Платежи не найдены')


if __name__ == "__main__":
    from mongoengine_connections import register_mongoengine_connections

    register_mongoengine_connections()
    get_sber_payers(datetime(2020, 12, 1), datetime(2021, 3, 1))
