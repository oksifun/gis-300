from processing.models.billing.provider.main import Provider
from utils.crm_utils import get_crm_client_ids


def get_clients_sber_codes(logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    result = [
        [
            'ИНН',
            'Наименование организации',
            'Код услуги',
        ],
    ]
    if table_print:
        table_print(';'.join(result[0]))
    providers = Provider.objects(
        pk__in=clients_ids,
    ).only(
        'str_name',
        'inn',
        'bank_accounts',
    ).as_pymongo()
    for provider in providers:
        codes = []
        for account in provider.get('bank_accounts', []):
            if account.get('service_codes'):
                codes.extend(account['service_codes'])
        row = [
            provider.get('inn') or '',
            provider['str_name'],
            ', '.join(codes),
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
