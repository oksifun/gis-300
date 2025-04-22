import datetime

from mongoengine import Q

from app.crm.models.crm import CRM
from app.area.models.area import Area
from processing.models.billing.accrual import Accrual
from app.house.models.house import House
from processing.models.billing.house_group import HouseGroup
from processing.models.billing.provider.main import Provider
from processing.models.billing.own_contract import OwnContract
from processing.models.billing.responsibility import Responsibility
from processing.models.billing.services_handbook import OwnServiceHandbook
from settings import ZAO_OTDEL_PROVIDER_OBJECT_ID
from utils.crm_utils import get_crm_client_ids


def get_client_from_date(date, logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    result = [
        [
            'ИНН',
            'Наименование организации',
        ],
    ]
    if table_print:
        table_print(';'.join(result[0]))
    provider_by_date = OwnContract.objects(
        client__in=clients_ids,
        date__gte=date,
    ).distinct(
        'client',
    )
    for provider_id in provider_by_date:
        provider = Provider.objects(
            pk=provider_id,
        ).only(
            'id',
            'str_name',
            'inn',
        ).as_pymongo().first()
        row = [
            provider.get('inn') or '',
            provider['str_name'],
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))


def get_clients_count_by_contract_type(month, logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    result = [
        [
            'Печать квитанций',
            'SaaS',
        ],
    ]
    print_services = []
    saas_services = []
    own_services = OwnServiceHandbook.objects.all()
    for service in own_services:
        if 'печать' in service.name.lower():
            print_services.append(service.pk)
        if 'saas' in service.description.lower():
            saas_services.append(service.pk)
    if table_print:
        table_print(';'.join(result[0]))
    contracts = OwnContract.objects(client__in=clients_ids).as_pymongo()
    saas_count = 0
    print_count = 0
    for contract in contracts:
        has_saas_service = False
        has_print_service = False
        if contract and len(contract.get('agreements') or []) > 0:
            last_agreement = sorted(
                contract['agreements'],
                key=lambda i: i['date'],
            )[-1]
            for service in last_agreement['services']:
                if service['service'] in saas_services:
                    has_saas_service = True
                if service['service'] in print_services:
                    has_print_service = True
        if has_saas_service:
            areas = Accrual.objects(
                doc__provider=contract['client'],
                month=month,
            ).distinct(
                'account.area.id',
            )
            areas = Area.objects(pk__in=areas).only('area_total').as_pymongo()
            saas_count += sum(a['area_total'] for a in areas)
        if has_print_service:
            print_count += Accrual.objects(
                doc__provider=contract['client'],
                month=month,
            ).count()
    result.append([str(print_count), str(saas_count)])
    if table_print:
        for row in result:
            table_print(';'.join(row))
    return result


def get_clients_stats(region_codes=None,
                      logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    query = {
        'owner': ZAO_OTDEL_PROVIDER_OBJECT_ID,
        'status': {'$in': ['client', 'debtor']},
    }
    clients_ids = CRM.objects(
        __raw__=query,
    ).distinct(
        'provider._id',
    )
    if logger:
        logger(f'Клиентов {len(clients_ids)}')
    if region_codes:
        region_query = Q(inn__startswith=region_codes[0])
        for ix in range(1, len(region_codes)):
            region_query = region_query | Q(inn__startswith=region_codes[ix])
        match_query = Q(id__in=clients_ids) & region_query
        clients_ids = Provider.objects(
            match_query,
        ).distinct(
            'id',
        )
    result = [
        [
            'Кол-во л/с',
            'Количество клиентов',
            'Количество МКД',
        ],
    ]
    date = datetime.datetime.now()
    responsibles = Responsibility.objects(
        __raw__={
            'provider': {'$in': clients_ids},
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
    ).aggregate(
        {
            '$group': {
                '_id': '$account._id',
            },
        },
        {
            '$group': {
                '_id': '',
                'count': {'$sum': 1},
            },
        },
    )
    responsibles = list(responsibles)[0]['count']
    house_groups = HouseGroup.objects(
        provider__in=clients_ids,
    ).distinct(
        'id',
    )
    houses = House.objects(_binds__hg__in=house_groups).count()
    result.append(
        [
            str(responsibles),
            str(len(clients_ids)),
            str(houses),
        ],
    )
    if table_print:
        for row in result:
            table_print(';'.join(row))
    return result
