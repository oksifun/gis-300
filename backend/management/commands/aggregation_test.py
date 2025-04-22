from bson import ObjectId

from mongoengine_connections import register_mongoengine_connections
from processing.models.billing.accrual import Accrual
from processing.models.billing.payment import Payment


def get_accruals():
    houses = [
        ObjectId("52623758e0e34c5239829d9b"),
        ObjectId("526237d1e0e34c523982c22f")
    ]
    match = {
        'account.area.house._id': {'$in': houses},
        'doc.status': {'$in': ['ready', 'edit']},
        'is_deleted': {'$ne': True}
    }
    aggregation_pipeline = [
        {'$match': match},
        {'$project': {
            '_id': 1,
            'house_id': '$account.area.house._id',
            'value': 1,
            'doc_date': '$doc.date',
            'month': {'$month': '$doc.date'},
            'year': {'$year': '$doc.date'}
        }},
        {'$group': {
            '_id': {'house_id': '$house_id', 'year': '$year',
                    'month': '$month'},
            'value': {'$sum': '$value'}
        }},
        {'$lookup': {
            'from': 'House',
            'localField': '_id.house_id',
            'foreignField': '_id',
            'as': 'house'
        }},
        {'$project': {
            '_id': 0,
            'house_id': '$_id.house_id',
            'address': '$house.address',
            'month': '$_id.month',
            'year': '$_id.year',
            'value': 1,
        }},
    ]
    accruals = list(Accrual.objects.aggregate(*aggregation_pipeline))
    return accruals
    # for accrual in accruals:
    #     print(accrual)


def get_payments():
    houses = [
        ObjectId("52623758e0e34c5239829d9b"),
        ObjectId("526237d1e0e34c523982c22f"),
    ]
    match = {
        'account.area.house._id': {'$in': houses},
        'is_deleted': {'$ne': True}
    }
    aggregation_pipeline = [
        {'$match': match},
        {'$project': {
            '_id': 1,
            'house_id': '$account.area.house._id',
            'value': 1,
            'doc_date': '$doc.date',
            'month': {'$month': '$doc.date'},
            'year': {'$year': '$doc.date'}
        }},
        {'$group': {
            '_id': {'house_id': '$house_id', 'year': '$year',
                    'month': '$month'},
            'value': {'$sum': '$value'}
        }},
        {'$lookup': {
            'from': 'House',
            'localField': '_id.house_id',
            'foreignField': '_id',
            'as': 'house'
        }},
        {'$project': {
            '_id': 0,
            'house_id': '$_id.house_id',
            'address': '$house.address',
            'month': '$_id.month',
            'year': '$_id.year',
            'value': 1,
        }},
    ]
    payments = list(Payment.objects.aggregate(*aggregation_pipeline))
    return payments


def get_combined_data(accruals, payments):
    houses = {}
    for accrual in accruals:
        house_data = houses.setdefault(
            accrual['house_id'],
            {
                'house_id': accrual['house_id'],
                'address': accrual['address'][0],
            }
        )
        house_data[f"accrual_{accrual['year']}_{accrual['month']}"] = \
            accrual['value']
    for payment in payments:
        house_data = houses.setdefault(
            payment['house_id'],
            {
                'house_id': payment['house_id'],
                'address': payment['address'][0],
            }
        )
        house_data[f"payment_{payment['year']}_{payment['month']}"] = \
            payment['value']
    result = houses.values()
    return result


if __name__ == "__main__":
    register_mongoengine_connections()
    accruals = get_accruals()
    for accrual in accruals:
        print(accrual)
    payments = get_payments()
    for payment in payments:
        print(payment)
    combined_data = get_combined_data(accruals, payments)
