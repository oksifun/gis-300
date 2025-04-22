from app.crm.models.crm import CRMStatus
from processing.models.billing.own_contract import OwnContract
from processing.models.billing.responsibility import Responsibility
from processing.models.billing.services_handbook import OwnServiceHandbook


CLIENT_STATUSES = (
    CRMStatus.CLIENT,
    CRMStatus.DEBTOR,
)


def _get_print_services():
    print_services = []
    own_services = OwnServiceHandbook.objects.all()
    for service in own_services:
        if 'печать' in service.name.lower():
            print_services.append(service.pk)
    return print_services


def _get_gis_services():
    print_services = []
    own_services = OwnServiceHandbook.objects.all()
    for service in own_services:
        if 'ГИС' in service.name.lower():
            print_services.append(service.pk)
    return print_services


def _has_print_service(provider_id, print_services_ids):
    contract = OwnContract.objects(client=provider_id).first()
    if contract and len(contract.agreements) > 0:
        last_agreement = sorted(
            contract.agreements,
            key=lambda i: i.date,
        )[-1]
        for service in last_agreement.services:
            if service.service.id in print_services_ids:
                return True
    return False


def _has_gis_service(provider_id, gis_services_ids):
    contract = OwnContract.objects(client=provider_id).first()
    if contract and len(contract.agreements) > 0:
        last_agreement = sorted(
            contract.agreements,
            key=lambda i: i.date,
        )[-1]
        for service in last_agreement.services:
            if service.service.id in gis_services_ids:
                return True
    return False


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
