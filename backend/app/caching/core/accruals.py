from processing.models.billing.accrual import Accrual
from processing.models.billing.account import Account


def get_house_accruals_by_aggregate(provider_id, house_id, month, sector):
    match_query = {
        'month': month,
        'sector_code': sector,
        'owner': provider_id,
        'account.area.house._id': house_id,
        'doc.status': {'$in': ['ready', 'edit']},
        'is_deleted': {'$ne': True},
    }
    aggregation_pipeline = [
        {
            '$match': match_query,
        },
        {
            '$project': {
                'services': 1,
                'month': 1,
                'sector_code': 1,
            },
        },
        {
            '$unwind': '$services',
        },
        {
            '$project': {
                'month': 1,
                'sector_code': 1,
                'service': '$services.service_type',
                'total': {'$add': [
                    '$services.value',
                    '$services.totals.recalculations',
                    '$services.totals.shortfalls',
                    '$services.totals.privileges',
                ]},
                'value': '$services.value',
                'recalculations': '$services.totals.recalculations',
                'shortfalls': '$services.totals.shortfalls',
                'privileges': '$services.totals.privileges',
                'consumption': '$services.consumption',
                'tariff': '$services.tariff',
            },
        },
        {
            '$project': {
                'month': 1,
                'sector_code': 1,
                'service': 1,
                'value': 1,
                'recalculations': 1,
                'shortfalls': 1,
                'privileges': 1,
                'consumption': 1,
                'tariff': 1,
                'total': 1,
                'debt': {'$max': ['$total', 0]},
            },
        },
        {
            '$group': {
                '_id': {
                    's': '$service',
                    'm': '$month',
                    'sc': '$sector_code',
                },
                't': {'$sum': '$total'},
                'd': {'$sum': '$debt'},
                'v': {'$sum': '$value'},
                'r': {'$sum': '$recalculations'},
                'p': {'$sum': '$privileges'},
                's': {'$sum': '$shortfalls'},
                'c': {'$sum': '$consumption'},
                'tar': {'$addToSet': '$tariff'},
            },
        },
    ]
    accruals = list(
        Accrual.objects.hint(
            'account.area.house._id_1',
        ).aggregate(
            *aggregation_pipeline,
        ),
    )
    return accruals


def get_house_accruals(provider_id, house_id, month, sector):
    # получаем жителей дома
    tenants = Account.objects(
        area__house__id=house_id,
    ).as_pymongo().only(
        'id',
        'is_developer',
    )
    tenants = {t['_id']: t for t in tenants}
    # получаем начисления по дому
    match_query = {
        'month': month,
        'sector_code': sector,
        'owner': provider_id,
        'account.area.house._id': house_id,
        'is_deleted': {'$ne': True},
    }
    accruals = Accrual.objects(
        __raw__=match_query
    ).hint(
        'account.area.house._id_1_month_1',
    ).as_pymongo().only(
        'account.id',
        'services.service_type',
        'services.value',
        'services.totals.recalculations',
        'services.totals.shortfalls',
        'services.totals.privileges',
        'services.consumption',
        'services.tariff',
        'totals.penalties',
        'doc.status',
    )

    def sum_dict(result_dict, service):
        data = result_dict['services'].setdefault(
            service['service_type'],
            {
                't': 0,
                'd': 0,
                'v': 0,
                'r': 0,
                'p': 0,
                's': 0,
                'c': 0,
                'tar': set(),
            },
        )
        total = (
                service['value']
                + service['totals']['recalculations']
                + service['totals']['shortfalls']
                + service['totals']['privileges']
        )
        data['t'] += total
        if total > 0:
            data['d'] += total
        data['v'] += service['value']
        data['r'] += service['totals']['recalculations']
        data['p'] += service['totals']['privileges']
        data['s'] += service['totals']['shortfalls']
        data['c'] += service['consumption']
        data['tar'].add(service['tariff'])

    result_all = {'services': {}, 'penalties': 0}
    result_no_dev = {'services': {}, 'penalties': 0}
    result_not_run = {'services': {}, 'penalties': 0}
    for a in accruals:
        if a['doc']['status'] == 'wip':
            for s in a['services']:
                sum_dict(result_not_run, s)
            result_not_run['penalties'] += a['totals']['penalties']
            continue
        for s in a['services']:
            sum_dict(result_all, s)
        result_all['penalties'] += a['totals']['penalties']
        if not tenants[a['account']['_id']].get('is_developer'):
            for s in a['services']:
                sum_dict(result_no_dev, s)
            result_no_dev['penalties'] += a['totals']['penalties']
    return {
        'all': result_all,
        'no_developer': result_no_dev,
        'not_run': result_not_run,
    }

