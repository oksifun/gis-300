from lib.helpfull_tools import by_mongo_path
from processing.models.billing.account import Account
from processing.models.billing.house_group import HouseGroup


def search_news_victims(recipients: dict):
    """Проверка наличия непрочитанных новостей"""
    # Жертвы новостей
    providers = by_mongo_path(recipients, 'providers.ids')
    houses = by_mongo_path(recipients, 'houses.ids')
    fias = by_mongo_path(recipients, 'houses.address_fias')
    workers_positions = by_mongo_path(recipients, 'workers.position_codes')
    victim_types = by_mongo_path(recipients, 'recipients_types')
    _type = []
    if 'for_tenants' in victim_types:
        _type.append('Tenant')
    if 'for_providers' in victim_types:
        _type.append('Worker')

    # Поиск групп домов
    hg_query = dict(provider__in=providers)
    if houses and not fias:
        hg_query.update(dict(houses__in=houses))
    # Группы домов организации
    hg = HouseGroup.objects(**hg_query).distinct('id')

    # Фильтр для работников
    worker_filter = {
        '_binds_permissions.pr': {'$in': providers}
    }
    # Фильтр для жителей
    tenant_filter = (
        {'_binds.hg': {'$in': hg}, 'area.house._id': {'$in': houses}}
        if houses and not fias
        else {'_binds.hg': {'$in': hg}}
    )
    # Если поиск по ФИАСу
    if fias:
        worker_filter.update({'_binds_permissions.fi': {'$in': fias}})
        tenant_filter.update({'_binds.fi': {'$in': fias}})
    else:
        worker_filter.update({'_binds_permissions.hg': {'$in': hg}})

    # Если есть должностной фильтр
    if workers_positions:
        worker_filter.update(
            {'_binds_permissions.dt': {'$in': workers_positions}}
        )
    query = {
        '_type': {'$in': _type},
        'has_access': True,
        'activation_code': None,
        'activation_step': None,
        '$or': [tenant_filter, worker_filter]
    }
    accounts = Account.objects(__raw__=query).distinct('id')
    return accounts
