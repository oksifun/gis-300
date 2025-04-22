import csv

from bson import ObjectId

from processing.models.billing.provider.main import Provider
from app.fiscalization.models.online_cash import OnlineCashPreferences
from processing.models.billing.own_contract import OwnContract

CASH_SERVICE = ObjectId("5c98829510de780013c7622c")


def get_provider_info(provider_ids):
    providers = Provider.objects(id__in=provider_ids).only('id', 'str_name')
    return {item.id: item.str_name for item in providers}


def get_cashes_info():
    cashes = OnlineCashPreferences.objects().only('owner', 'cash').all()
    return {item.owner: len(item.cash.devices) for item in cashes}


def get_own_contracts_info(client_ids):
    contracts = OwnContract.objects(
        client__in=client_ids).only('client', 'agreements').all().as_pymongo()
    contracts_info = dict()
    for item in contracts:
        if not item.get('agreements'):
            continue
        for agreement in item['agreements']:
            if not agreement.get('services'):
                continue
            for service in agreement['services']:
                if service['service'] == CASH_SERVICE:
                    contracts_info.setdefault(item['client'], 0)
                    contracts_info[item['client']] += 1
    return contracts_info


def extract_cashier_info(filename):
    rows = list()
    cashes_dict = get_cashes_info()
    provider_ids = list(cashes_dict.keys())
    providers_dict = get_provider_info(provider_ids)
    contract_dict = get_own_contracts_info(provider_ids)

    for k, v in cashes_dict.items():
        rows.append([k, providers_dict[k], v, contract_dict.get(k, 0)])
    with open(filename, mode='w') as f:
        writer = csv.writer(f, delimiter=';',
                            quotechar='"',
                            quoting=csv.QUOTE_NONNUMERIC
                            )
        writer.writerows(rows)


if __name__ == "__main__":
    from mongoengine_connections import register_mongoengine_connections

    register_mongoengine_connections()
    filename = 'provider_cashier.csv'
    extract_cashier_info(filename)
