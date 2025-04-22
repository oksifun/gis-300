from bson import ObjectId
from app.legal_entity.models.legal_entity import LegalEntity
from app.legal_entity.models.legal_entity_contract import LegalEntityContract
from app.legal_entity.models.legal_entity_service import EntityAgreementService
from app.offsets.models.offset import Offset
from processing.data_producers.associated.services import get_service_names
from processing.models.billing.accrual import Accrual
from datetime import datetime


def get_services(p_id):
    pipeline = [{'$match': {
        'provider': p_id,
        'is_deleted': {'$ne': True}
    }},
        {'$lookup': {
            'from': 'House',
            'localField': 'house',
            'foreignField': '_id',
            'as': 'house_data'
        }},
        {'$unwind': '$house_data'},
        {'$project': {
            'address': '$house_data.address',
            'entity': 1,
            'contract': 1,
            'agreement': 1,
            'service': 1,
            'house': 1,
            'date_from': 1,
            'date_till': 1,
            'service_select_type': 1
        }},
        {'$sort': {
            'address': 1,
            'agreement': 1,
            'entity': 1,
            'service': 1
        }}]
    services_cursor = EntityAgreementService.objects.aggregate(
        *pipeline, allowDiskUse=True)
    services = list(services_cursor)
    return services


def get_agreements(agreements_ids):
    pipeline = [{'$match': {'agreements._id': {'$in': agreements_ids}}},
                {'$unwind': '$agreements'}]
    contracts = LegalEntityContract.objects.aggregate(*pipeline)
    return {c['agreements']['_id']: c['agreements'] for c in contracts}


def get_entities(entity_ids):
    return {item.id: item.current_details.current_name for item in
            LegalEntity.objects(id__in=entity_ids)}


def get_debit_sum(contract, house, service, provider, date_from, date_till):
    if service == 'penalties':
        return _get_penalties_sum(contract,
                                  house,
                                  provider,
                                  date_from,
                                  date_till)
    else:
        return _get_accruals_sum(contract,
                                 house,
                                 service,
                                 provider,
                                 date_from,
                                 date_till)


def _get_penalties_sum(contract, house, provider, date_from, date_till):
    penalties_pipeline = [{'$match': {
        '_binds.pr': provider,
        'account.area.house._id': house,
        'doc.status': {'$in': ['ready', 'edit']},
        'is_deleted': {'$ne': True},
        'doc.date': {'$gte': date_from, '$lte': date_till},
        'penalty_vendor.contract': contract
    }},
        {'$project': {
            'value': '$totals.penalties'
        }}]
    accruals = Accrual.objects.aggregate(*penalties_pipeline)
    total = 0
    for accrual in accruals:
        if accrual['value'] > 0:
            total += accrual['value']
    return round(total / 100, 2)


def _get_accruals_sum(contract, house, service, provider, date_from, date_till):
    pipeline = [
        {'$match': {
            '_binds.pr': provider,
            'account.area.house._id': house,
            'doc.status': {'$in': ['ready', 'edit']},
            'is_deleted': {'$ne': True},
            'doc.date': {'$gte': date_from, '$lte': date_till}
        }},
        {'$unwind': '$services'},
        {'$project': {
            'services': 1
        }},
        {'$match': {
            'services.vendor.contract': contract,
            'services.service_type': service
        }}]

    accruals = Accrual.objects.aggregate(*pipeline)
    total = 0
    for accrual in accruals:
        accrual_sum = (
                accrual['services']['value']
                + accrual['services']['totals']['recalculations']
                + accrual['services']['totals']['shortfalls']
                + accrual['services']['totals']['privileges']
        )
        if accrual_sum > 0:
            total += accrual_sum
    return round(total / 100, 2)


def get_credit_sum(contract, house, service, provider, date_from, date_till):
    if service == 'penalties':
        return _get_penalties_offsets_sum(contract, house,
                                          provider,
                                          date_from,
                                          date_till)
    else:
        return _get_offsets_sum(contract,
                                house,
                                service,
                                provider,
                                date_from,
                                date_till)


def _get_penalties_offsets_sum(contract, house, provider, date_from, date_till):
    pipeline = [{'$match': {
        'refer.account.area.house._id': house,
        '_binds.pr': provider,
        '_type': {'$nin': ['Refund', 'Advance']},
        'refer.doc.date': {'$gte': date_from, '$lte': date_till},
        'is_pennies': True
    }},
        {'$unwind': '$services'},
        {'$project': {
            'services': 1
        }},
        {'$match': {
            'services.vendor.contract': contract,
        }}]

    offsets = Offset.objects.aggregate(*pipeline)
    total = 0
    for offset in offsets:
        total += offset['services']['value']
    return round(total / 100, 2)


def _get_offsets_sum(contract, house, service, provider, date_from, date_till):
    pipeline = [{'$match': {
        'refer.account.area.house._id': house,
        '_binds.pr': provider,
        '_type': {'$nin': ['Refund', 'Advance']},
        'refer.doc.date': {'$gte': date_from, '$lte': date_till}
    }},
        {'$unwind': '$services'},
        {'$project': {
            'services': 1
        }},
        {'$match': {
            'services.vendor.contract': contract,
            'services.service_type': service
        }}]

    offsets = Offset.objects.aggregate(*pipeline)
    total = 0
    for offset in offsets:
        total += offset['services']['value']
    return round(total / 100, 2)


def get_stat(provider_id, date_from, date_till):
    services = get_services(provider_id)
    agreements = get_agreements([s['agreement'] for s in services])
    entities = get_entities([s['entity'] for s in services])

    service_types_ids = []
    for s in services:
        if s.get('service_select_type') in ['penalties', 'advance']:
            s['service'] = s.get('service_select_type')
        service_types_ids.append(s['service'])

    services_title = get_service_names(provider_id, service_types_ids,
                                       old_style=True)

    for service in services:
        d_f = service['date_from'] if service['date_from'] > date_from \
            else date_from
        if service['date_till']:
            d_t = service['date_till'] if service['date_till'] < date_till \
                else date_till
        else:
            d_t = date_till

        accruals_sum = get_debit_sum(service['contract'],
                                     service['house'],
                                     service['service'],
                                     provider_id, d_f, d_t)
        offsets_sum = get_credit_sum(service['contract'],
                                     service['house'],
                                     service['service'],
                                     provider_id, d_f, d_t)

        try:
            if offsets_sum or accruals_sum:
                line = [
                    entities[service['entity']],
                    agreements[service['agreement']]['number'],
                    service['address'],
                    agreements[service['agreement']]['date'].strftime(
                        '%d.%m.%Y'),
                    (
                        agreements[service['agreement']]['date_till'].strftime(
                            '%d.%m.%Y') if
                        agreements[service['agreement']]['date_till'] else ''
                    ),
                    services_title[service['service']]['title'],
                    service['date_from'].strftime('%d.%m.%Y'),
                    (service['date_till'].strftime('%d.%m.%Y')
                     if service['date_till'] else ''),
                    accruals_sum,
                    offsets_sum
                ]
                print(';'.join(map(str, line)))
        except KeyError:
            # заглушка от услуг с договором в другой коллекции
            # в 221 неполные данные
            continue


if __name__ == "__main__":
    from mongoengine_connections import register_mongoengine_connections

    register_mongoengine_connections()
    date_from = datetime.strptime('01.06.2019', '%d.%m.%Y')
    date_till = datetime.strptime('31.05.2021', '%d.%m.%Y')
    provider_id = ObjectId("5c9346e443cf66002dd04daa")
    get_stat(provider_id, date_from, date_till)
