from app.area.models.area import Area
from app.meters.models.meter import AreaMeter
from processing.models.billing.settings import Settings


def get_house_settings(house_id, providers_ids):
    accrual_settings = Settings.objects(
        _type='ProviderAccrualSettings',
        provider__in=providers_ids,
        house=house_id,
    ).as_pymongo()
    return {s['provider']: s for s in accrual_settings}


def get_house_stats(house_id):
    agg_pipeline = [
        {'$match': {
            'area.house._id': house_id,
            '_type': 'HeatAreaMeter',
            'is_deleted': {'$ne': True},
        }},
        {'$project': {
            'area._id': 1,
            'area_type': {'$cond': [
                {'$lte': [{'$size': '$area._type'}, 2]},
                {'$arrayElemAt': ['$area._type', 0]},
                {'$arrayElemAt': ['$area._type', -2]},
            ]},
        }},
        {'$group': {
            '_id': '$area._id',
            'area_type': {'$first': '$area_type'},
        }},
        {'$group': {
            '_id': '$area_type',
            'count': {'$sum': 1},
        }},
    ]
    meters = list(AreaMeter.objects.aggregate(*agg_pipeline))
    meters = {m['_id']: m['count'] for m in meters}
    agg_pipeline = [
        {'$match': {
            'house._id': house_id,
            'is_deleted': {'$ne': True},
        }},
        {'$project': {
            'area_type': {'$cond': [
                {'$lte': [{'$size': '$_type'}, 2]},
                {'$arrayElemAt': ['$_type', 0]},
                {'$arrayElemAt': ['$_type', -2]},
            ]},
        }},
        {'$group': {
            '_id': '$area_type',
            'count': {'$sum': 1},
        }},
    ]
    areas = list(Area.objects.aggregate(*agg_pipeline))
    areas = {a['_id']: a['count'] for a in areas}
    result = {
        'areas_count_living': areas.get('LivingArea', 0),
        'heat_meters_count_living': meters.get('LivingArea', 0),
        'areas_count_not_living': areas.get('NotLivingArea', 0),
        'heat_meters_count_not_living': meters.get('NotLivingArea', 0),
        'areas_count_parking': areas.get('ParkingArea', 0),
    }
    result['areas_count'] = \
        result['areas_count_living'] + result['areas_count_not_living']
    result['heat_meters_count'] = \
        result['heat_meters_count_living'] \
        + result['heat_meters_count_not_living']
    # проценты
    if result['areas_count']:
        result['heat_meters_percent'] = \
            result['heat_meters_count'] / result['areas_count'] * 100
    else:
        result['heat_meters_percent'] = 0
    if result['areas_count_living']:
        result['heat_meters_percent_living'] = \
            result['heat_meters_count_living'] \
            / result['areas_count_living'] * 100
    else:
        result['heat_meters_percent_living'] = 0
    if result['areas_count_not_living']:
        result['heat_meters_percent_not_living'] = \
            result['heat_meters_count_not_living'] \
            / result['areas_count_not_living'] * 100
    else:
        result['heat_meters_percent_not_living'] = 0
    return result
