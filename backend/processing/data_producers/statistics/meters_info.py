from app.area.models.area import Area
from app.meters.models.meter import AreaMeter


def get_houses_meters_statistics(date, houses: list, binds=None):
    """Статистика по квартирам с просроченными счетчиками"""
    query = {
            'area.house._id': {'$in': houses},
            'next_check_date': {'$lte': date},
            '$or': [
                {'working_finish_date': None},
                {'working_finish_date': {'$gt': date}},
            ]}
    if binds:
        query.update(AreaMeter.get_binds_query(query, raw=True))

    meters = list(AreaMeter.objects(__raw__=query).only('area').as_pymongo())
    # Общее количество квартир в каждом доме
    areas_total = {h: Area.objects(house__id=h).count() for h in houses}
    areas_meter = _get_areas_meter(houses)
    # Подсчитываем количество квартир с просроченными счетчиками
    _areas_overdue = {}
    for meter in meters:
        h_id = meter['area']['house']['_id']
        aid = meter['area']['_id']
        _areas_overdue.setdefault(h_id, {}).setdefault(aid, 0)
        _areas_overdue[h_id][aid] += 1
    areas_overdue = {k: len(v.values()) for k, v in _areas_overdue.items()}

    # Собираем все данные с группировкой по домам
    data = {}
    for h_id in areas_total.keys() | areas_meter.keys() | areas_overdue.keys():
        h_data = data.setdefault(str(h_id), {})
        h_data['total'] = areas_total.get(h_id, 0)
        h_data['metered'] = areas_meter.get(h_id, 0)
        h_data['overdue'] = areas_overdue.get(h_id, 0)
    return data


def _get_areas_meter(houses_ids: list):
    """
    Количество квартир с установленными счетчиками в каждом доме
    """
    pipeline = [
        {'$match': {'area.house._id': {'$in': houses_ids}}},
        {'$group': {
            '_id': {
                'area': '$area._id',
                'house': '$area.house._id'
            },
            'meters': {'$sum': 1}
        }
        },
        {'$group': {
            '_id': '$_id.house',
            'count': {'$sum': 1}
        }}
    ]
    area_meters = list(AreaMeter.objects.aggregate(*pipeline))
    return {x['_id']: x['count'] for x in area_meters}
