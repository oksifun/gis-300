from mongoengine import Q

from app.crm.models.crm import CRM
from processing.models.billing.account import Tenant
from processing.models.billing.provider.main import Provider
from settings import ZAO_OTDEL_PROVIDER_OBJECT_ID
from utils.crm_utils import get_crm_client_ids


def get_tenant_emails(logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    result = [
        [
            'email',
        ],
    ]
    if table_print:
        table_print(';'.join(result[0]))
    emails = Tenant.objects(
        _type='Tenant',
        email__nin=[None, ''],
    ).distinct(
        'email',
    )
    for email in emails:
        row = [email]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def get_clients_emails(statuses=None, not_statuses=None, region_codes=None,
                       logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    query = {'owner': ZAO_OTDEL_PROVIDER_OBJECT_ID}
    if statuses:
        query['status'] = {'$in': statuses}
    elif not_statuses:
        query['status'] = {'$nin': not_statuses}
    clients_ids = get_crm_client_ids()
    if logger:
        logger(f'Клиентов {len(clients_ids)}')
    match_query = (
            Q(
                    _type__ne='BankProvider',
                    id__in=clients_ids,
            )
            & (
                    Q(email__nin=[None, ''])
                    | Q(chief__email__nin=[None, ''])
            )
    )
    if region_codes:
        region_query = Q(inn__startswith=region_codes[0])
        for ix in range(1, len(region_codes)):
            region_query = region_query | Q(inn__startswith=region_codes[ix])
        match_query = match_query & region_query
    providers = Provider.objects(
        match_query,
    ).only(
        'id',
        'inn',
        'str_name',
        'email',
        'chief.email',
    ).as_pymongo()
    if logger:
        logger(f'Email-ов организаций {providers.count()}')
    result = [
        [
            'ИНН',
            'Наименование организации',
            'id',
            'email',
        ],
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for provider in providers:
        emails = {provider.get('email')}
        emails.add(provider.get('chief', {}).get('email'))
        for email in emails:
            if not email:
                continue
            row = [
                provider.get('inn') or '',
                provider.get('str_name') or '',
                str(provider['_id']),
                email,
            ]
            result.append(row)
            if table_print:
                table_print(';'.join(row))
    return result


def get_not_clients_emails(not_statuses=None, logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    if not not_statuses:
        not_statuses = [
            'client',
            'wrong',
            'alien',
            'ban',
        ]
    no_clients_ids = CRM.objects(
        __raw__={
            'status': {'$nin': not_statuses},
            'owner': ZAO_OTDEL_PROVIDER_OBJECT_ID,
        },
    ).distinct(
        'provider._id',
    )
    providers = Provider.objects(
        pk__in=no_clients_ids,
        _type__ne='BankProvider',
    ).only(
        'id',
        'inn',
        'str_name',
        'email',
        'accountant',
        'chief',
    ).as_pymongo()
    if logger:
        logger(f'Получено {providers.count()}')
    title_row = [
        'Наименование',
        'ИНН',
        'Email организации',
        'ФИО руководителя',
        'Должность руководителя',
        'Email руководителя',
        'ФИО бухгалтера',
        'Email бухгалтера',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for provider in providers:
        if not provider.get('chief'):
            provider['chief'] = {}
        if not provider.get('accountant'):
            provider['accountant'] = {}
        row = [
            provider.get('str_name') or '',
            provider.get('inn') or '',
            provider.get('email') or '',
            provider['chief'].get('str_name') or '',
            provider['chief'].get('position', {}).get('name') or '',
            provider['chief'].get('email') or '',
            provider['accountant'].get('str_name') or '',
            provider['accountant'].get('email') or '',
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result
