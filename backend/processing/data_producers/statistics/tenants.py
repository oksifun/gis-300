from processing.models.billing.account import Tenant


def get_houses_tenants_statistics(houses_ids: list, binds=None):
    """Статистика по жителям в домах"""
    # Собираем все данные с группировкой по домам
    phones = _get_phones(houses_ids, binds)
    has_access = _get_tenant_with_access(houses_ids, binds)
    data = {}
    for house in phones:
        h_data = data.setdefault(
            house['_id'],
            {'has_phone': 0, 'has_access': 0}
        )
        h_data['has_phone'] = house['count']
    for house in has_access:
        h_data = data.setdefault(
            house['_id'],
            {'has_phone': 0, 'has_access': 0}
        )
        h_data['has_access'] = house['count']
    return data


def _get_phones(houses_ids: list, binds):
    query = {
        'phones': {'$exists': True, '$not': {'$size': 0}},
        'area.house._id': {'$in': houses_ids}
    }
    if binds:
        query.update(Tenant.get_binds_query(query, raw=True))
    agg_pipeline = [
        {'$match': query},
        {'$group': {
            '_id': '$area.house._id',
            'count': {'$sum': 1},
        }},
    ]
    phone_count = list(Tenant.objects.aggregate(*agg_pipeline))
    return phone_count


def _get_tenant_with_access(houses_ids, binds):
    query = {
        'has_access': True,
        'activation_code': {'$exists': False},
        'activation_step': {'$exists': False},
        'area.house._id': {'$in': houses_ids}
    }
    if binds:
        query.update(Tenant.get_binds_query(query, raw=True))
    agg_pipeline = [
        {'$match': query},
        {'$group': {
            '_id': '$area.house._id',
            'count': {'$sum': 1},
        }},
    ]
    access_count = list(Tenant.objects.aggregate(*agg_pipeline))
    return access_count
