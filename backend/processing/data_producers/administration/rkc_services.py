from bson import ObjectId

from app.legal_entity.models.legal_entity import LegalEntity
from app.legal_entity.models.legal_entity_contract import LegalEntityContract
from app.legal_entity.models.legal_entity_service import EntityAgreementService
from app.offsets.models.offset import Offset
from processing.data_producers.balance.base import CONDUCTED_STATUSES
from processing.models.billing.accrual import Accrual
from app.accruals.models.accrual_document import AccrualDoc


def get_contracts(provider_id):
    return LegalEntityContract.objects(provider=provider_id)


def get_entities(entity_ids):
    return {item.id: item.current_details.current_name for item in
            LegalEntity.objects(id__in=entity_ids)}


def get_houses_from_services(agreement_id):
    return EntityAgreementService.objects(
        agreement=agreement_id).distinct('house')


def get_accrual_docs(house_id, provider_id):
    return AccrualDoc.objects(
        house__id=house_id,
        _binds__pr=provider_id,
        status__in=CONDUCTED_STATUSES,
    ).only(
        'id',
        'date',
        'date_from',
        'house',
    ).order_by(
        'date',
    ).as_pymongo()


def get_accruals_sum(accrual_doc_id, contract_id, provider_id):
    accruals = Accrual.objects(
        doc__id=accrual_doc_id,
        _binds__pr=provider_id
    ).only(
        'id',
        'services',
    ).as_pymongo()
    total = 0
    for accrual in accruals:
        for service in accrual['services']:
            if not service.get('vendor'):
                continue
            if service['vendor'].get('contract') == contract_id:
                total += (
                    service['value']
                    + service['totals']['recalculations']
                    + service['totals']['shortfalls']
                    + service['totals']['privileges']
                )
    return round(total / 100, 2), [i['_id'] for i in accruals]


def get_offsets_sum(accrual_ids, contract_id, provider_id):
    offsets = Offset.objects(__raw__={
        'accrual._id': {'$in': accrual_ids},
        '_binds.pr': provider_id,
        '_type': {'nin': ['Refund', 'Advance']},
    }

    ).only(
        'id',
        'services',
    ).as_pymongo()
    total = 0
    for offset in offsets:
        for service in offset['services']:
            if not service.get('vendor'):
                continue
            if service['vendor'].get('contract') == contract_id:
                total += service['value']
    return round(total / 100, 2)


def get_stat(provider_id):
    contracts = get_contracts(provider_id)
    entities = get_entities([c.entity for c in contracts])
    for contract in contracts:
        entity = entities[contract.entity]
        for agreement in contract.agreements:
            houses = get_houses_from_services(agreement.id)
            for house in houses:
                if not house:
                    continue
                prev_accrual_doc_date = None
                accrual_docs = get_accrual_docs(house, provider_id)
                temp = list()
                for a_doc in accrual_docs:
                    current_accrual_doc_date = \
                        a_doc['date_from'].strftime('%m.%Y')
                    accruals_sum, accrual_ids = get_accruals_sum(
                        a_doc['_id'],
                        contract.id,
                        provider_id,
                    )
                    offsets_sum = get_offsets_sum(accrual_ids, contract.id,
                                                  provider_id)
                    if current_accrual_doc_date == prev_accrual_doc_date:
                        temp[-1][-2] += accruals_sum
                        temp[-1][-1] += offsets_sum
                    else:
                        line = [
                            entity,
                            contract.number,
                            a_doc['house']['address'],
                            agreement.date.strftime('%d.%m.%Y'),
                            (
                                agreement.date_till.strftime('%d.%m.%Y')
                                if agreement.date_till else ''
                            ),
                            current_accrual_doc_date,
                            accruals_sum,
                            offsets_sum,
                        ]
                        temp.append(line)
                        prev_accrual_doc_date = current_accrual_doc_date
                for row in temp:
                    row[-1] = str(row[-1]).replace('.', ',')
                    row[-2] = str(row[-2]).replace('.', ',')
                    print(';'.join(map(str, row)))


if __name__ == "__main__":
    from mongoengine_connections import register_mongoengine_connections

    register_mongoengine_connections()

    provider_id = ObjectId("5c9346e443cf66002dd04daa")
    get_stat(provider_id)
