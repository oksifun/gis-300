import datetime

from processing.data_producers.associated.base import get_binded_houses
from processing.data_producers.export.administration.base import \
    _get_responsibles
from processing.models.billing.provider.main import Provider
from processing.models.billing.own_contract import OwnContract
from processing.models.billing.services_handbook import OwnServiceHandbook
from processing.models.tasks.gis.base import GisBaseExportRequest
from utils.crm_utils import get_crm_client_ids


def get_client_services_stat(logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    providers = Provider.objects(
        pk__in=clients_ids,
    ).only(
        'id',
        'inn',
        'str_name',
        'online_cash',
    ).as_pymongo()
    table = []
    gis_services = []
    print_services = []
    own_services = OwnServiceHandbook.objects.all()
    for service in own_services:
        if 'ГИС' in service.name:
            gis_services.append(service.pk)
        if 'печать' in service.name.lower():
            print_services.append(service.pk)
    date = datetime.datetime.now()
    title_row = [
        'Наименование',
        'ИНН',
        'Кол-во ЛС',
        'Касса',
        'ГИС',
        'Печать квитанций',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for provider in providers:
        contract = OwnContract.objects(client=provider['_id']).first()
        has_gis_service = False
        has_print_service = False
        if contract and len(contract.agreements) > 0:
            last_agreement = sorted(
                contract.agreements,
                key=lambda i: i.date,
            )[-1]
            for service in last_agreement.services:
                if service.service.id in gis_services:
                    has_gis_service = True
                if service.service.id in print_services:
                    has_print_service = True
        resp = _get_responsibles(provider['_id'], date)
        table.append(
            (
                provider['inn'],
                provider['str_name'],
                str(len(resp)),
                _bool_to_text(
                    provider.get('online_cash', {}).get('active'),
                ),
                _bool_to_text(has_gis_service),
                _bool_to_text(has_print_service),
            ),
        )
    if table_print:
        for row in table:
            logger(';'.join(row))


def get_client_no_cash(legal_form_exclude=None, logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    if legal_form_exclude:
        providers = Provider.objects(
            pk__in=clients_ids,
            legal_form__nin=legal_form_exclude,
        )
    else:
        providers = Provider.objects(pk__in=clients_ids)
    providers = providers.filter(
        online_cash__active__ne=True,
    ).only(
        'id',
        'inn',
        'str_name',
    ).as_pymongo()
    table = []
    for provider in providers:
        table.append(
            (
                provider['inn'],
                provider['str_name'],
            ),
        )
    if table_print:
        for row in table:
            logger(';'.join(row))


def get_client_gis_service_stat(logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    providers = Provider.objects(
        pk__in=clients_ids,
    ).only(
        'id',
        'inn',
        'str_name',
        'online_cash',
    ).as_pymongo()
    table = []
    gis_services = []
    own_services = OwnServiceHandbook.objects.all()
    for service in own_services:
        if 'ГИС' in service.name:
            gis_services.append(service.pk)
    for provider in providers:
        contract = OwnContract.objects(client=provider['_id']).first()
        has_gis_service = False
        if contract and len(contract.agreements) > 0:
            last_agreement = sorted(
                contract.agreements,
                key=lambda i: i.date,
            )[-1]
            for service in last_agreement.services:
                if service.service.id in gis_services:
                    has_gis_service = True
        gis_task = list(
            GisBaseExportRequest.objects(
                provider=provider['_id'],
            ).order_by(
                '-created',
            ).only(
                'created',
            ).as_pymongo()[0: 1]
        )
        if gis_task:
            date = gis_task[0]['created'].strftime("%d.%m.%Y")
        else:
            date = ''
        table.append(
            (
                provider['inn'],
                provider['str_name'],
                _bool_to_text(has_gis_service),
                str(len(get_binded_houses(provider['_id']))),
                date,
            ),
        )
    if table_print:
        for row in table:
            logger(';'.join(row))


def _bool_to_text(bool_value):
    return 'Да' if bool_value else 'Нет'
