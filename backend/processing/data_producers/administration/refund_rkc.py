from datetime import datetime

from bson import ObjectId
from dateutil.relativedelta import relativedelta

from processing.data_producers.forms.binded_houses import (
    get_providers_binded_houses
)
from processing.models.billing.account import Tenant
from processing.models.billing.payment import Payment


def get_accounts_info(account_ids):
    result = dict()
    tenant_info = Tenant.objects(
        pk__in=account_ids).only('str_name', 'area').as_pymongo()
    for item in tenant_info:
        result[item['_id']] = {
            'str_name': item['str_name'],
            'address': f"{item['area']['house']['address']}, "
                       f"{item['area']['str_number_full']}"
        }
    return result


def get_payments_data(params, house_id):
    match = {
        'account.area.house._id': house_id,
        'date': {
            '$gte': params['date_from'],
            '$lt': params['date_to'] + relativedelta(days=1),
        },
        'sector_code': {'$in': params['sectors']},
        'is_deleted': {'$ne': True},
        '_binds.pr': {'$in': [params['provider']]}
    }
    aggregation_pipeline = [
        {'$match': match},
        {'$project': {
            '_id': 1,
            'account': '$account._id',
            'area': '$account.area.order',
            'bank_date': '$doc.date',
            'sector': '$sector_code',
            'date': 1,
            'value': 1,
        }},
        {'$sort': {
            'area': 1
        }},
        {'$group': {
            '_id': {
                'account': '$account',
            },
            'values': {'$push': '$$ROOT'},
            'total': {'$sum': '$value'}
        }},
    ]
    return list(Payment.objects.aggregate(*aggregation_pipeline))


def get_rows(params):
    houses = get_providers_binded_houses(params['provider'],
                                         params['date_from'])
    hs = [ObjectId(f"{item['house_id']}") for item in houses]
    for house in hs:
        payments = get_payments_data(params, house)
        if not payments:
            continue
        accounts_info = get_accounts_info(
            [x['_id']['account'] for x in payments]
        )

        for item in payments:
            if item['total'] >= 0:
                continue
            positive = list()
            negative = list()
            for x in item['values']:
                if x['value'] > 0:
                    positive.append(x)
                else:
                    negative.append(x)

            positive = [z['value'] for z in positive]
            negative = sorted(negative, key=lambda a: a['value'])
            res = list()

            for n in negative:
                if abs(n['value']) not in positive:
                    res.append(n)
            if not res:
                continue
            acc_info = accounts_info[item['_id']['account']]
            for val in res:
                if val['date'] < val['bank_date']:
                    row = [
                        acc_info['address'],
                        acc_info['str_name'],
                        round(val['value'] / 100, 2),
                        datetime.strftime(val['bank_date'], '%d-%m-%Y'),
                        datetime.strftime(val['date'], '%d-%m-%Y'),
                    ]
                    print(';'.join(map(str, row)))


if __name__ == "__main__":
    from mongoengine_connections import register_mongoengine_connections

    register_mongoengine_connections()
    params = {
        'sectors': ["rent", "garbage"],
        'date_from': datetime(2000, 1, 1),
        'date_to': datetime(2021, 6, 30),
        'provider': ObjectId('5e5513244157870012251929')
    }
    get_rows(params)

