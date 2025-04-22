import datetime

from app.auth.models.actors import Actor
from app.house.models.house import House
from processing.data_producers.associated.base import get_binded_houses
from processing.models.billing.payment import PaymentDoc
from processing.models.billing.provider.main import BankProvider, Provider
from processing.models.billing.responsibility import Responsibility
from processing.models.choices import ProcessingType
from utils.crm_utils import get_crm_client_ids


def get_clients_list(logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    providers = Provider.objects(
        __raw__={
            '_id': {'$in': clients_ids},
        },
    ).only(
        'id',
        'inn',
        'str_name',
        'address',
    ).order_by(
        '-str_name',
    ).as_pymongo()
    if logger:
        print('Нашла', providers.count())
    title_row = [
        'Наименование',
        'ИНН',
        'Фактический адрес',
        'Юридический адрес',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for provider in providers:
        row = [
            provider['str_name'],
            provider.get('inn') or '',
            Provider.get_address_string_by_dict(provider, 'real'),
            Provider.get_address_string_by_dict(provider, 'postal'),
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def get_clients_by_bic_of_bank_account(bic_number,
                                       logger=None, table_print=None):
    bank = BankProvider.objects(
        bic_body__BIC=bic_number,
    ).get()
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    providers = list(
        Provider.objects(
            __raw__={
                '_id': {'$in': clients_ids},
                'bank_accounts.bic': bank.id,
            },
        ).only(
            'id',
            'inn',
            'str_name',
        ).order_by(
            '-str_name',
        ).as_pymongo(),
    )
    title_row = [
        'Наименование',
        'ИНН',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for provider in providers:
        row = [
            provider.get('inn') or '',
            provider['str_name'],
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def get_clients_with_sber_info(date_from, logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    providers = Provider.objects(
        __raw__={
            '_id': {'$in': clients_ids},
        },
    ).only(
        'id',
        'inn',
        'str_name',
        'address',
    ).order_by(
        '-str_name',
    ).as_pymongo()
    if logger:
        print('Нашла', providers.count())
    title_row = [
        'Наименование',
        'ИНН',
        'Всего ответственных',
        'Количество ЛКЖ',
        'Есть ли реестры Сбербанка',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for provider in providers:
        pay_doc = PaymentDoc.objects(
            provider=provider['_id'],
            _type='SberDoc',
            date__gte=date_from,
        ).only(
            'id',
        ).as_pymongo().first()
        resp = len(_get_responsibles(provider['_id'], date_from))
        cabinets = _get_cabinets_queryset_by_provider(provider['_id']).count()
        row = [
            provider['str_name'],
            provider.get('inn') or '',
            str(resp),
            str(cabinets),
            'да' if pay_doc else 'нет'
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def _get_clients_queryset_by_bic(bic_number):
    bank = BankProvider.objects(
        bic_body__BIC=bic_number,
    ).get()
    clients_ids = get_crm_client_ids()
    return (
        bank,
        Provider.objects(
            __raw__={
                '_id': {'$in': clients_ids},
                'bank_accounts': {
                    '$elemMatch': {
                        'bic': bank.id,
                        'active_till': None,
                    },
                },
            },
        ).order_by(
            '-str_name',
        ).as_pymongo(),
    )


def _get_cabinets_queryset_by_provider(provider_id):
    return Actor.objects(
        provider__id=provider_id,
        has_access=True,
        owner__owner_type='Tenant',
    )


def _get_responsibles(provider_id, date):
    return Responsibility.objects(
        __raw__={
            'provider': provider_id,
            '$and': [
                {
                    '$or': [
                        {'date_from': None},
                        {'date_from': {'$lte': date}},
                    ],
                },
                {
                    '$or': [
                        {'date_till': None},
                        {'date_till': {'$gte': date}},
                    ],
                },
            ],
        },
    ).distinct('account.id')


def get_clients_with_openbank_code(logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    providers = Provider.objects(
        __raw__={
            '_id': {'$in': clients_ids},
        },
    ).only(
        'id',
        'inn',
        'ogrn',
        'kpp',
        'str_name',
        'bank_accounts',
    ).order_by(
        '-str_name',
    ).as_pymongo()
    if logger:
        print('Нашла', providers.count())
    title_row = [
        'Наименование',
        'ИНН',
        'ОГРН',
        'КПП',
        'Расчетный счет',
        'Код Открытия',
        'БИК',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    banks = {}
    now = datetime.datetime.now()
    for provider in providers:
        for bank_account in provider['bank_accounts']:
            if bank_account.get('active_till'):
                if bank_account['active_till'] < now:
                    continue
            bank = banks.get(bank_account['bic'])
            if bank is None:
                bank = BankProvider.objects(
                    pk=bank_account['bic'],
                ).only(
                    'bic_body',
                ).as_pymongo().first()
                if bank:
                    bank = bank['bic_body'][0]['BIC']
                else:
                    bank = ''
                banks[bank_account['bic']] = bank
            openbank_code = ''
            for service in bank_account.get('processing_services', []):
                if service.get('type') == ProcessingType.OTKRITIE:
                    openbank_code = service['code']
                    break
            row = [
                provider.get('inn') or '',
                provider['str_name'],
                provider.get('ogrn') or '',
                provider.get('kpp') or '',
                bank_account['number'],
                openbank_code,
                bank,
            ]
            result.append(row)
            if table_print:
                table_print(';'.join(row))
    return result


def get_clients_no_ban(logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    providers = list(
        Provider.objects(
            __raw__={
                '_id': {'$in': clients_ids},
                'disable_when_debtor': False,
            },
        ).only(
            'id',
            'inn',
            'str_name',
        ).order_by(
            '-str_name',
        ).as_pymongo(),
    )
    title_row = [
        'Наименование',
        'ИНН',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for provider in providers:
        row = [
            provider.get('inn') or '',
            provider['str_name'],
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def get_clients_with_houses_count(logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    providers = Provider.objects(
        __raw__={
            '_id': {'$in': clients_ids},
        },
    ).only(
        'id',
        'inn',
        'str_name',
    ).order_by(
        '-str_name',
    ).as_pymongo()
    if logger:
        print('Нашла', providers.count())
    title_row = [
        'Наименование',
        'ИНН',
        'Кол-во домов',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for provider in providers:
        houses = get_binded_houses(provider['_id'])
        row = [
            provider['str_name'],
            provider.get('inn') or '',
            str(len(houses)),
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def get_clients_with_houses_areas(logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    providers = Provider.objects(
        __raw__={
            '_id': {'$in': clients_ids},
        },
    ).only(
        'id',
        'inn',
        'str_name',
    ).order_by(
        '-str_name',
    ).as_pymongo()
    if logger:
        print('Нашла', providers.count())
    title_row = [
        'Наименование',
        'ИНН',
        'Адрес',
        'Полезная площадь дома',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for provider in providers:
        houses = get_binded_houses(provider['_id'])
        houses = House.objects(
            id__in=houses,
        ).only(
            'address',
            'area_total',
        ).as_pymongo()
        for house in houses:
            area = house.get('area_total', 0)
            if not isinstance(area, str):
                area = str(round(area, -2))
            row = [
                provider['str_name'],
                provider.get('inn') or '',
                house['address'],
                area,
            ]
            result.append(row)
            if table_print:
                table_print(';'.join(row))
    return result
