from datetime import datetime

from processing.models.billing.payment import PaymentDoc
from processing.models.billing.provider.main import Provider
from utils.crm_utils import get_crm_client_ids


def sber_stat(date_from, date_till):
    clients_ids = get_crm_client_ids(include_debtors=True)
    title_row = [
        'Организация',
        'ИНН',
        'Тип платежей'
    ]
    providers_dict = {x.id: x for x in Provider.objects(
        id__in=clients_ids).only('str_name', 'inn')
    }

    sber = list(PaymentDoc.objects(__raw__={
        'date': {'$gte': date_from,
                 '$lt': date_till},
        'is_deleted': {'$ne': True},
        '$and': [{'_type': 'RegistryDoc'}, {'_type': 'SberDoc'}],
        '_binds.pr': {'$in': clients_ids}
    }).only('_binds', 'provider').as_pymongo())

    with_sber = set()
    for item in sber:
        for pr in item['_binds']['pr']:
            with_sber.add(pr)

    non_sber = set(clients_ids) - with_sber
    result = {
        'реестры Сбер': with_sber,
        'единичные платежи': non_sber,
    }
    for pay_type, clients_group in result.items():
        print(';'.join(title_row))
        for item in clients_group:
            if not providers_dict.get(item):
                continue
            obj = providers_dict[item]
            row = [
                obj['str_name'],
                obj['inn'],
                pay_type
            ]
            print(';'.join(row))
        print('\n')


if __name__ == "__main__":
    from mongoengine_connections import register_mongoengine_connections

    register_mongoengine_connections()
    sber_stat(datetime(2021, 6, 1), datetime(2021, 6, 30))
