from mongoengine import Q

from app.crm.models.crm import CRM
from app.personnel.models.personnel import Worker
from processing.models.billing.provider.main import Provider
from settings import ZAO_OTDEL_PROVIDER_OBJECT_ID
from utils.crm_utils import get_crm_client_ids


def get_clients_phones_by_receipt_type(receipt_type, logger=None,
                                       table_print=None):
    providers = Provider.objects(
        receipt_type=receipt_type,
    ).only(
        'id',
        'inn',
        'str_name',
        'phones',
        'accountant',
        'chief',
        'receipt_type',
    ).as_pymongo()
    if logger:
        logger(f'Получено {providers.count()}')
    title_row = [
        'Наименование',
        'ИНН',
        'Телефон организации',
        'ФИО руководителя',
        'телефоны руководителя',
        'e-mail руководителя',
        'ФИО бухгалтера',
        'e-mail бухгалтера',
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
            provider['str_name'],
            provider['inn'],
            format_phones_list(provider['phones']),
            provider['chief'].get('str_name') or '',
            (
                format_phones_list(provider['chief']['phones'])
                if provider['chief'].get('phones')
                else ''
            ),
            provider['chief'].get('email') or '',
            provider['accountant'].get('str_name') or '',
            provider['accountant'].get('email') or '',
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def get_not_clients_ceo_phones(logger=None, table_print=None):
    no_clients_ids = CRM.objects(
        __raw__={
            'status': {
                '$in': [
                    'new',
                    'cold',
                    'work',
                    'prospective_client',
                    'denied',
                ],
            },
            'owner': ZAO_OTDEL_PROVIDER_OBJECT_ID,
        },
    ).distinct(
        'provider._id',
    )
    providers = Provider.objects(
        pk__in=no_clients_ids,
    ).only(
        'id',
        'inn',
        'str_name',
        'phones',
        'accountant',
        'chief',
    ).as_pymongo()
    if logger:
        logger(f'Получено {providers.count()}')
    title_row = [
        'Название организации',
        'ИНН',
        'ФИО Директора',
        'Телефон директора',
        'ФИО бухгалтера',
        'Телефон бухгалтера',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for provider in providers:
        if not provider.get('str_name') or not provider.get('inn'):
            continue
        row = [
            provider['str_name'],
            provider['inn'],
        ]
        chief = []
        accountant = []
        if provider.get('chief') and provider['chief'].get('phones'):
            phones = format_phones_list(provider['chief']['phones'])
            if phones:
                chief.append(provider['chief'].get('str_name') or '')
                chief.append(phones)
        if provider.get('accountant') and provider['accountant'].get('phones'):
            phones = format_phones_list(provider['accountant']['phones'])
            if phones:
                accountant.append(provider['accountant'].get('str_name') or '')
                accountant.append(phones)
        if not chief and not accountant:
            continue
        if chief:
            row.extend(chief)
        else:
            row.append('')
            row.append('')
        if accountant:
            row.extend(accountant)
        else:
            row.append('')
            row.append('')
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def _format_phone(phone):
    return '{}{}{}'.format(
        '+7{}'.format(phone['code']) if phone.get('code') else '',
        phone.get('number') or '',
        ' доб.{}'.format(phone['add']) if phone.get('add') else ''
    )


def format_phones_list(phones):
    return ', '.join([_format_phone(ph) for ph in phones])


def get_not_clients_phones(not_statuses, region_codes, logger=None,
                           table_print=None):
    if logger:
        logger('Получение исходных данных')
    no_clients_ids = CRM.objects(
        __raw__={
            'status': {'$nin': not_statuses},
            'owner': ZAO_OTDEL_PROVIDER_OBJECT_ID,
        },
    ).distinct(
        'provider._id',
    )
    region_query = Q(inn__startswith=region_codes[0])
    for ix in range(1, len(region_codes)):
        region_query = region_query | Q(inn__startswith=region_codes[ix])
    providers = Provider.objects(
        Q(pk__in=no_clients_ids) & region_query
    ).only(
        'id',
        'inn',
        'str_name',
        'phones',
        'accountant.phones',
        'chief.phones',
        'receipt_type',
    ).as_pymongo()
    if logger:
        logger(f'Получено {providers.count()}')
    title_row = [
        'ИНН',
        'Наименование организации',
        'id',
        'Телефон',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for provider in providers:
        phones = set()
        phone_lists = (
            provider.get('phones', []),
            provider.get('chief', {}).get('phones', []),
            provider.get('accountant', {}).get('phones', []),
        )
        for phone_list in phone_lists:
            for phone in phone_list:
                if phone.get('code'):
                    number = f'8{phone["code"]}{phone["number"]}'
                else:
                    number = phone.get("number")
                if number:
                    phones.add(number)
        for phone in phones:
            row = [
                provider.get('inn') or '',
                provider.get('str_name') or '',
                str(provider['_id']),
                phone,
                # provider.get('receipt_type') or '',
            ]
            result.append(row)
            if table_print:
                table_print(';'.join(row))
    return result


def get_not_clients_phones_special(report_type=1,
                                   logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    if report_type == 1:
        q = Q(
            receipt_type__in=[
                'self',
                'other',
                'ellis',
                'vzkp',
                'sberbank',
                'eirclo',
                'inari',
                'r200',
            ],
        )
    else:
        q = Q(
            receipt_type__nin=[
                'self',
                'other',
                'ellis',
                'vzkp',
                'sberbank',
                'eirclo',
                'inari',
                'r200',
            ],
        )
    providers = Provider.objects(
        (Q(inn__startswith='78') | Q(inn__startswith='47'))
        & q
        & Q(pk__nin=clients_ids)
    ).only(
        'id',
        'inn',
        'str_name',
        'phones',
        'accountant.phones',
        'chief.phones',
        'receipt_type',
    ).as_pymongo()
    if logger:
        logger(f'Получено {providers.count()}')
    title_row = [
        'ИНН',
        'Наименование организации',
        'id',
        'Телефон',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for provider in providers:
        phones = set()
        phone_lists = (
            provider.get('phones', []),
            provider.get('chief', {}).get('phones', []),
            provider.get('accountant', {}).get('phones', []),
        )
        for phone_list in phone_lists:
            for phone in phone_list:
                if phone.get('code'):
                    number = f'8{phone["code"]}{phone["number"]}'
                else:
                    number = phone.get("number")
                if number:
                    phones.add(number)
        for phone in phones:
            row = [
                provider.get('inn') or '',
                provider.get('str_name') or '',
                str(provider['_id']),
                phone,
                # provider.get('receipt_type') or '',
            ]
            result.append(row)
            if table_print:
                table_print(';'.join(row))
    return result
