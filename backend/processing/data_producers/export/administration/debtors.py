from processing.data_producers.balance.base import CONDUCTED_STATUSES
from processing.models.billing.accrual import Accrual
from processing.models.billing.payment import Payment
from utils.crm_utils import get_crm_client_ids


def get_balance_champions(legal_entities=False, logger=None):
    clients_ids = get_crm_client_ids()
    if logger:
        logger(f'Клиентов {len(clients_ids)}')
    balance_max = 0
    balance_min = 0
    account_max = None
    account_min = None
    accruals_query = {
        'sector_code': 'rent',
        'doc.status': {'$in': CONDUCTED_STATUSES},
        'is_deleted': {'$ne': True},
        'account.is_developer': {'$ne': True},
    }
    payments_query = {
        'sector_code': 'rent',
        'is_deleted': {'$ne': True},
        'account.is_developer': {'$ne': True},
    }
    if not legal_entities:
        accruals_query['account._type'] = 'PrivateTenant'
        payments_query['account._type'] = 'PrivateTenant'
    for provider in clients_ids:
        accruals_query['owner'] = provider
        accruals = Accrual.objects(
            __raw__=accruals_query,
        ).aggregate(
            {
                '$group': {
                    '_id': '$account._id',
                    'value': {'$sum': '$value'},
                },
            },
        )
        payments_query['doc.provider'] = provider
        payments = Payment.objects(
            __raw__=payments_query,
        ).aggregate(
            {
                '$group': {
                    '_id': '$account._id',
                    'value': {'$sum': '$value'},
                },
            },
        )
        payments = {p['_id']: p['value'] for p in payments}
        for ix, accrual in enumerate(accruals, start=1):
            val = accrual['value'] - payments.get(accrual['_id'], 0)
            if val > balance_max:
                balance_max = val
                account_max = accrual['_id']
            if val < balance_min:
                balance_min = val
                account_min = accrual['_id']
            if ix % 1000 == 0:
                print(account_max, balance_max, account_min, balance_min)
        print(account_max, balance_max, account_min, balance_min)
