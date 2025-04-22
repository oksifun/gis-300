from app.accruals.cipca.calculator.tariffs import get_groups_list


def get_cache_services_cold_water(pipca_doc):
    return pipca_doc.get_services_by_head_type('water_individual')


def get_cache_services_hot_water(pipca_doc):
    return pipca_doc.get_services_by_head_type('heating_water_individual')


def get_cache_services_heat_water(pipca_doc):
    return pipca_doc.get_services_by_head_type('heat_water')


def get_cache_services_heat_water_other(pipca_doc):
    return list(
        set(pipca_doc.get_services_by_head_type('heat_water'))
        - set(pipca_doc.get_services_by_head_type('hot_water'))
        - set(pipca_doc.get_services_by_head_type('hot_water_public'))
    )


def get_cache_services_heat(pipca_doc):
    return pipca_doc.get_services_by_head_type('heat')


def get_cache_services_electricity(pipca_doc):
    return pipca_doc.get_services_by_head_type('electricity_individual')


def get_cache_services_cold_water_public(pipca_doc):
    return pipca_doc.get_services_by_head_type('water_public')


def get_cache_services_hot_water_public(pipca_doc):
    return pipca_doc.get_services_by_head_type('heating_water_public')


def get_cache_services_electricity_public(pipca_doc):
    return pipca_doc.get_services_by_head_type('electricity_public')


def get_cache_services_waste_water(pipca_doc):
    return pipca_doc.get_services_by_head_type('waste_water')


def get_cache_services_gas(pipca_doc):
    return pipca_doc.get_services_by_head_type('gas_supply')


def get_service_groups_by_pipca(pipca_doc):
    result = {}
    for tp in pipca_doc.tariff_plans:
        for tariff in tp['tariffs']:
            if tariff['service_type'] not in result:
                result[tariff['service_type']] = tariff['group']
    return result


def get_cache_services_by_group(pipca_doc, group):
    tariff_groups = get_groups_list(group)
    service_groups = get_service_groups_by_pipca(pipca_doc)
    return [k for k, v in service_groups.items() if v in tariff_groups]


def get_cache_services_housing(pipca_doc):
    return get_cache_services_by_group(pipca_doc, 0)


def get_cache_services_other(pipca_doc):
    return get_cache_services_by_group(pipca_doc, 2)


def get_cache_services_communal(pipca_doc):
    return get_cache_services_by_group(pipca_doc, 1)


def get_cache_services_capital_repair(pipca_doc):
    return get_cache_services_by_group(pipca_doc, 3)


def get_cache_services_communal_other_services(pipca_doc):
    return list(
        set(get_cache_services_by_group(pipca_doc, 3))
        - set(pipca_doc.get_services_by_head_type('communal_services'))
    )


SERVICE_GROUP_CACHE_FUNCS = {
    'housing': get_cache_services_housing,
    'other': get_cache_services_other,
    'communal': get_cache_services_communal,
    'capital_repair': get_cache_services_capital_repair,
    'cold_water': get_cache_services_cold_water,
    'hot_water': get_cache_services_hot_water,
    'heat_water': get_cache_services_heat_water,
    'heat_water_other': get_cache_services_heat_water_other,
    'heat': get_cache_services_heat,
    'electricity': get_cache_services_electricity,
    'cold_water_public': get_cache_services_cold_water_public,
    'hot_water_public': get_cache_services_hot_water_public,
    'electricity_public': get_cache_services_electricity_public,
    'waste_water': get_cache_services_waste_water,
    'gas': get_cache_services_gas,
    'communal_other_services': get_cache_services_communal_other_services,
}
