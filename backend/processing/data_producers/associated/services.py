from bson import ObjectId
from mongoengine import DoesNotExist

from processing.data_producers.forms.tariff_plan import \
    get_provider_tariffs_tree
from processing.data_producers.public.services import get_system_services
from processing.models.billing.tariff_plan import TariffPlan
from processing.models.billing.service_type import ServiceType


PENALTY_SERVICE_TYPE = 'penalties'
ADVANCE_SERVICE_TYPE = 'advance'
_OLD_PENALTY_SERVICE_TYPE = ObjectId('0' * 24)
_OLD_ADVANCE_SERVICE_TYPE = ObjectId('1' * 24)
_PENALTY_SERVICE_DESCRIPTION = {
    'title': 'Пени',
    'group': 69,
    'okei': None,
}
_ADVANCE_SERVICE_DESCRIPTION = {
    'title': 'Аванс',
    'group': 69,
    'okei': None,
}


def get_all_service_names(provider_id):
    service_ids = (
            ServiceType.objects(provider=provider_id).distinct('id')
            + [i['id'] for i in get_system_services()]
    )
    data = get_service_names(
        provider_id=provider_id,
        service_type_ids=set(service_ids),
        not_s_types=True,
    )
    return data


def get_service_names(provider_id, service_type_ids, tariff_plans_ids=None,
                      not_s_types=None, as_list=False, old_style=False):
    result = {
        ObjectId(s): None
        for s in service_type_ids
        if s not in (PENALTY_SERVICE_TYPE, ADVANCE_SERVICE_TYPE)
    }
    if old_style:
        if _OLD_PENALTY_SERVICE_TYPE in service_type_ids:
            result[_OLD_PENALTY_SERVICE_TYPE] = _PENALTY_SERVICE_DESCRIPTION
        if _OLD_ADVANCE_SERVICE_TYPE in service_type_ids:
            result[_OLD_ADVANCE_SERVICE_TYPE] = _ADVANCE_SERVICE_DESCRIPTION
    if PENALTY_SERVICE_TYPE in service_type_ids:
        result[PENALTY_SERVICE_TYPE] = _PENALTY_SERVICE_DESCRIPTION
    if ADVANCE_SERVICE_TYPE in service_type_ids:
        result[ADVANCE_SERVICE_TYPE] = _ADVANCE_SERVICE_DESCRIPTION
    if tariff_plans_ids:
        tariffs = _get_tariffs_by_plans(tariff_plans_ids, list(result.keys()))
        for tariff in tariffs:
            if result[tariff['_id']]:
                continue
            result[tariff['_id']] = tariff
    # сначала извлечём названия из текущего дерева
    try:
        tariffs_tree = get_provider_tariffs_tree(provider_id)
        _fill_titles_from_node(tariffs_tree[0], result)
    except DoesNotExist:
        pass
    # если не всё заполнено, ищем в тарифных планах
    if not all(result.values()):
        left_services = [s for s, t in result.items() if not t]
        tariffs = _get_last_tariffs(provider_id, left_services)
        for tariff in tariffs:
            if tariff['_id'] not in left_services:
                continue
            if result[tariff['_id']]:
                continue
            result[tariff['_id']] = tariff
    # если по-прежнему есть неизвестные - берём наименования услуг
    if not_s_types:
        if as_list:
            return _convert_to_list(result)
        return result
    if not all(result.values()):
        left_services = [s for s, t in result.items() if not t]
        s_types = ServiceType.objects(pk__in=left_services).as_pymongo()
        for s_type in s_types:
            if result[s_type['_id']]:
                continue
            result[s_type['_id']] = {
                '_id': s_type['_id'],
                'title': s_type['title'],
                'group': 2,
                'okei': None,
            }
    if as_list:
        return _convert_to_list(result)
    return result


def _convert_to_list(services_dict):
    result = []
    for service_id, service_data in services_dict.items():
        if service_data:
            service_data['id'] = service_id
            result.append(service_data)
    result.sort(key=lambda i: (i['group'], i['title']))
    return result


def _fill_titles_from_node(source_node, target_services):
    if all(target_services.values()):
        return
    if 'tariffs' in source_node:
        for group in source_node['tariffs']:
            for tariff in group['tariffs']:
                if tariff['service_type'] not in target_services:
                    continue
                if target_services[tariff['service_type']]:
                    continue
                target_services[tariff['service_type']] = dict(
                    title=tariff['title'],
                    group=group['group']
                )
    if 'nodes' in source_node:
        for node in source_node['nodes']:
            _fill_titles_from_node(node, target_services)


def _get_last_tariffs(provider_id, service_types_ids):
    agg_pipeline = [
        {'$match': {'provider': provider_id}},
        {'$project': {
            'date_from': 1,
            'tariffs.service_type': 1,
            'tariffs.title': 1,
            'tariffs.group': 1,
        }},
        {'$sort': {'date_from': -1}},
        {'$unwind': '$tariffs'},
        {'$project': {
            'date_from': 1,
            's_type': '$tariffs.service_type',
            'title': '$tariffs.title',
            'group': '$tariffs.group',
        }},
        {'$sort': {'_id': -1}},
        {'$sort': {'date_from': -1}},
        {'$group': {
            '_id': '$s_type',
            'title': {'$first': '$title'},
            'group': {'$first': '$group'},
            'okei': {'$first': '$units_okei'},
        }},
        {'$match': {'_id': {'$in': service_types_ids}}},
    ]
    return list(TariffPlan.objects.aggregate(*agg_pipeline, allowDiskUse=True))


def _get_tariffs_by_plans(tariff_plans_ids, service_types_ids):
    agg_pipeline = [
        {'$match': {'_id': {'$in': tariff_plans_ids}}},
        {'$project': {
            'date_from': 1,
            'tariffs.service_type': 1,
            'tariffs.title': 1,
            'tariffs.group': 1,
        }},
        {'$unwind': '$tariffs'},
        {'$project': {
            'date_from': 1,
            's_type': '$tariffs.service_type',
            'title': '$tariffs.title',
            'group': '$tariffs.group',
            '_id': 0,
        }},
        {'$sort': {'date_from': -1}},
        {'$group': {
            '_id': '$s_type',
            'title': {'$first': '$title'},
            'group': {'$first': '$group'},
            'okei': {'$first': '$units_okei'},
        }},
        {'$match': {'_id': {'$in': service_types_ids}}},
    ]
    return list(TariffPlan.objects.aggregate(*agg_pipeline))

