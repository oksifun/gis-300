import datetime

from app.legal_entity.models.legal_entity_contract import LegalEntityContract
from app.legal_entity.models.legal_entity_service import EntityAgreementService
from processing.models.choices import LegalDocumentType

_AREA_TYPE_NAMES_CONVERT = {
    'living_areas': 'LivingArea',
    'not_living_areas': 'NotLivingArea',
    'parking_areas': 'ParkingArea',
}


def build_vendors_dict(provider, house_id, date):
    query = {
        'provider': provider,
        'closed': {'$ne': True},
        '_type': {'$in': [
            LegalDocumentType.AGENT,
            LegalDocumentType.SERVICE,
        ]},
        'entity': {'$exists': True},
        'agreements': {'$exists': True}
    }
    legal_contracts = LegalEntityContract.objects(
        __raw__=query
    ).only('id').as_pymongo()
    contract_ids = [item['_id'] for item in legal_contracts]
    vendors_dict = {}
    services = EntityAgreementService.objects(
        __raw__={
            'contract': {'$in': contract_ids},
            'service': {'$exists': True},
        }
    ).as_pymongo()
    for service in services:
        date_from = service.get('date_from') or datetime.datetime.min
        date_till = service.get('date_till') or datetime.datetime.max
        if (
                service['house'] == house_id
                and date_from <= date <= date_till
        ):
            _update_vendors_dict_by_service(
                vendors_dict,
                service
            )

    return vendors_dict


def _update_vendors_dict_by_service(vendors_dict, service):
    for field in _AREA_TYPE_NAMES_CONVERT:
        if not service[field]:
            continue
        if not service['consider_developer']:
            developer_statuses = [False]
        else:
            developer_statuses = [True, False]
        vendors_dict.update(
            {
                (
                    service['service'],
                    _AREA_TYPE_NAMES_CONVERT[field],
                    status
                ): {
                    '_id': service['entity'],
                    'contract': service['contract']
                }
                for status in developer_statuses
            }
        )
