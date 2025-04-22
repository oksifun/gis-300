from dateutil.relativedelta import relativedelta

from processing.data_producers.balance.base import HouseAccountsBalance
from processing.data_producers.balance.services.accounts import \
    AccountsServicesHouseBalance
from app.offsets.models.offset import Offset
from processing.models.billing.accrual import Accrual


def get_offsets(house_id, sector, accounts_ids, date, month, binds=None):
    balance_calculator = HouseAccountsBalance(
        house=house_id,
        accounts_ids=accounts_ids,
        binds=binds,
    )
    balances = balance_calculator.get_date_balance(
        date_on=month,
        sectors=[sector],
        use_bank_date=False,
    )
    if date >= month:
        turnovers = balance_calculator.get_turnovers(
            date_from=month,
            date_till=date - relativedelta(days=1),
            sectors=[sector],
            use_bank_date=False,
        )
        reverse_turnovers = {}
    else:
        turnovers = {}
        reverse_turnovers = balance_calculator.get_turnovers(
            date_from=date,
            date_till=month - relativedelta(days=1),
            sectors=[sector],
            use_bank_date=False,
        )
    result = {}
    for account_id in accounts_ids:
        account_balance = balances.get(account_id, {}).get('val', 0)
        account_turnovers = turnovers.get(account_id, (0, 0))
        reverse_account_turnovers = reverse_turnovers.get(account_id, (0, 0))
        result[account_id] = {
            'month_start': account_balance,
            'current_date': (
                account_balance
                + account_turnovers[0]
                - account_turnovers[1]
                - reverse_account_turnovers[0]
                + reverse_account_turnovers[1]
            ),
            'turnovers': account_turnovers,
        }
    return result


def get_split_offsets(house_id, sector, accounts_ids, date, month):
    balance_calculator = AccountsServicesHouseBalance(
        None,
        house_id,
        accounts_ids=accounts_ids,
        sectors=[sector],
    )
    services_balance = {a: {} for a in accounts_ids}
    if date >= month:
        date_from = month
        date_till = date - relativedelta(days=1)
        turnovers_key = 'turnovers'
        zero_turnovers_key = 'cancel_turnovers'
    else:
        date_from = date
        date_till = month - relativedelta(days=1)
        turnovers_key = 'cancel_turnovers'
        zero_turnovers_key = 'turnovers'
    trial_balance = balance_calculator.get_trial_balance(
        date_from=date_from,
        date_till=date_till,
    )
    for account_service, data in trial_balance.items():
        if account_service[0] not in services_balance:
            continue
        services_balance[account_service[0]][account_service[1]] = {
            'month_start': data['balance_in'],
            'current_date': data['balance_out'],
            turnovers_key: (
                data['accruals'],
                data['refund'],
                data['payment'],
                data['refund'],
            ),
            zero_turnovers_key: (0, 0, 0, 0),
        }
    return services_balance


def get_values_for_refund(provider_id, sector, services_ids, accounts_ids,
                          date):
    accruals = _get_older_accruals(
        provider_id,
        sector,
        services_ids,
        accounts_ids,
        date,
    )
    refund_exists = _get_refund_exists(
        provider_id,
        sector,
        services_ids,
        accounts_ids,
        date,
    )
    for key, refund in refund_exists.items():
        if key in accruals:
            accruals[key] -= refund
    return accruals


def _get_refund_exists(provider_id, sector, services_ids, accounts_ids, date):
    agg_pipeline = [
        {
            '$match': {
                'refer.doc.provider': provider_id,
                'refer.sector_code': sector,
                'refer.account._id': {'$in': accounts_ids},
                'services.service_type': {'$in': services_ids},
                'refer.date': {'$lt': date},
                '_type': 'Refund',
            },
        },
        {
            '$project': {
                'refer.account._id': 1,
                'services': 1,
            },
        },
        {
            '$unwind': '$services',
        },
        {
            '$match': {
                'services.service_type': {'$in': services_ids},
            },
        },
        {
            '$group': {
                '_id': {
                    'account': '$refer.account._id',
                    'service': '$services.service_type',
                },
                'value': {'$sum': '$services.value'},
            },
        },
    ]
    data = Offset.objects.aggregate(*agg_pipeline)
    return {
        (d['_id']['account'], d['_id']['service']): d['value']
        for d in data if d['value']
    }


def _get_older_accruals(provider_id, sector, services_ids, accounts_ids, date):
    agg_pipeline = [
        {
            '$match': {
                'owner': provider_id,
                'sector_code': sector,
                'account._id': {'$in': accounts_ids},
                'services.service_type': {'$in': services_ids},
                'doc.date': {'$lt': date},
                'doc.status': {'$in': ['ready', 'edit']},
                'is_deleted': {'$ne': True},
            },
        },
        {
            '$project': {
                'account._id': 1,
                'services.result': 1,
                'services.service_type': 1,
                'services.reversal': 1,
            },
        },
        {
            '$unwind': '$services',
        },
        {
            '$match': {
                'services.service_type': {'$in': services_ids},
                'services.reversal': {'$ne': True},
            },
        },
        {
            '$group': {
                '_id': {
                    'account': '$account._id',
                    'service': '$services.service_type',
                },
                'value': {'$sum': '$services.result'},
            },
        },
    ]
    data = Accrual.objects.aggregate(*agg_pipeline)
    return {
        (d['_id']['account'], d['_id']['service']): d['value']
        for d in data if d['value']
    }
