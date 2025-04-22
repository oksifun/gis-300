from datetime import datetime

from app.caching.models.metabase_stat import NonSberRegistersStat
from processing.models.billing.payment import PaymentDoc
from utils.crm_utils import get_crm_client_ids


def get_stat(date_from, date_till):
    client_ids = get_crm_client_ids()
    pipeline = [
        {
            '$match': {
                'date': {'$gte': date_from,
                         '$lt': date_till},
                'is_deleted': {'$ne': True},
                '$and': [{'_type': 'RegistryDoc'}, {'_type': 'SberDoc'}],
                '_binds.pr': {'$in': client_ids}
            }
        },
        {
            '$project': {
                'month': {
                    '$dateToString': {'format': '%m.%Y', 'date': '$date'}},
                'prov': {'$arrayElemAt': ['$_binds.pr', 0]}
            }
        },
        {
            '$group': {
                '_id': {'month': '$month'},
                'provs': {'$addToSet': '$prov'}
            }
        },
        {
            '$project': {
                'month': '$_id.month',
                'cnt': {'$setDifference': [client_ids, '$provs']},
                '_id': 0
            }
        },
        {
            '$project': {
                'month': 1, 'cnt': {'$size': '$cnt'}
            }
        }
    ]
    result = list(PaymentDoc.objects.aggregate(*pipeline))
    for item in result:
        old = NonSberRegistersStat.objects(
            month=datetime.strptime(item['month'], '%m.%Y')
        ).first()
        if old:
            old.cnt = item['cnt']
            old.save()
        else:
            new = NonSberRegistersStat(
                month=datetime.strptime(item['month'], '%m.%Y'),
                cnt=item['cnt']
            )
            new.save()
