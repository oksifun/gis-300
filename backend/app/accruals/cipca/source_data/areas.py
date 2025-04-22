from fractions import Fraction

from bson import ObjectId
from dateutil.relativedelta import relativedelta

from app.area.models.area import Area
from lib.helpfull_tools import by_mongo_path
from processing.models.billing.account import Tenant
from processing.models.billing.responsibility import Responsibility


def get_areas_calculation_data(month, areas_ids, area_type=None):
    if area_type:
        areas = Area.objects.filter(
            id__in=areas_ids, _type=area_type
        ).as_pymongo()
    else:
        areas = Area.objects.filter(id__in=areas_ids).as_pymongo()
    return {
        a['_id']: a
        for a in areas.only(
            'id',
            'number',
            'num_letter',
            'num_alt',
            'num_desc',
            'area_total_history',
            'area_total',
            'area_living',
            'is_shared',
            'stove_type',
            'intercom',
            'rooms',
            'porch',
            'floor',
            'has_lift',
            'has_hw',
            'has_cw',
            'has_boiler',
            'has_bath',
            'has_ch',
            'area_common',
            'is_allowed_meters',
            'common_property',
            'parent_area',
        )
    }


def get_mates_calculation_data(month, areas_ids):
    return {a: {'living': 1, 'registered': 1} for a in areas_ids}


_TENANT_FIELDS = (
    'id',
    'area',
    'statuses',
    'family',
    'str_name',
    '_type',
    'number',
)
_TENANT_EXTRA_FIELD = (
    'birth_date',
    'sex',
    'last_name',
    'first_name',
    'patronymic_name',
    'snils',
)


def get_mates(month, provider_id, areas, extra_tenant_data=False) -> dict:
    # TODO: Реализовано только определение на 1 число месяца
    if not areas:
        return {}
    elif isinstance(areas, dict):
        areas_ids = list(areas.keys())
    elif isinstance(areas, (list, tuple)) and isinstance(areas[0], ObjectId):
        areas_ids = areas
    else:
        raise TypeError("Помещения жильцов в неопознанном формате")

    if extra_tenant_data:
        fields = _TENANT_FIELDS + _TENANT_EXTRA_FIELD
    else:
        fields = _TENANT_FIELDS

    mates = list(
        Tenant.objects(
            area__id__in=areas_ids,
            is_deleted__ne=True,
        ).only(
            *fields,
        ).as_pymongo(),
    )
    resp_areas = get_responsibles(
        provider_id,
        areas_ids,
        month,
        month + relativedelta(months=1),
    )

    result = find_result(mates, month, resp_areas)
    return result


_STATUSES_SUM_KEYS = ('registered', 'registered_const', 'living', 'ownership')


def _is_living(mate, month):
    # проживает ли
    status = {}
    for l in mate['statuses'].get('living', []):
        # на первое число
        if (
                ((l.get('date_from') or month) <= month) and
                ((l.get('date_till') or month) >= month)
        ):
            status['living'] = 1
    return status


def _is_registered(mate, month):
    # прописан ли
    status = {}
    for r in mate['statuses'].get('registration', []):
        # на первое число
        if (
                ((r.get('date_from') or month) <= month) and
                ((r.get('date_till') or month) >= month)
        ):
            status['registered'] = 1
            status['registered_const'] = 0 if (
                r['value']['is_temporary']
                if r.get('value')
                else None) else 1
            status['reg_start'] = r.get('date_from')
            status['reg_finish'] = r.get('date_till')
    return status


def _is_property_share(mate, month):
    # собственник ли
    status = {}
    if by_mongo_path(mate, 'statuses.ownership.property_share_history'):
        # на первое число
        share = get_property_share(
            mate['statuses']['ownership']['property_share_history'],
            month
        )
        if share > 0:
            status['ownership'] = 1
            status['property_share'] = share
    return status


def get_correct_area_total(area, date):
    """
    Находит актуальную площадь квартиры в определённый момент времени
    :param area:
    :param date:
    :return:
    """
    area_total_history = area['area_total_history']
    if len(area_total_history) == 1:
        return area.get('area_total', 0)
    else:
        for total in reversed(area_total_history):
            if total['date'] <= date:
                return total['value']
        return area['area_total']


def get_share_square(mate, month, area):
    total_square = get_correct_area_total(area, month)
    try:
        props = mate['statuses']['ownership']['property_share_history']
        share = get_property_share(props, month)
        share_square = total_square * share
    except (TypeError, KeyError):
        share_square = total_square
    return share_square


def find_result(mates, month, resp_areas):
    result = {}
    area_ids = [m['area']['_id'] for m in mates]
    areas = get_areas_calculation_data(month, area_ids)
    for mate in mates:
        if not mate.get('statuses'):
            continue
        status = {}
        status.update(_is_living(mate, month))
        status.update(_is_registered(mate, month))
        status.update(_is_property_share(mate, month))
        share_square = get_share_square(mate, month, areas[mate['area']['_id']])
        status['share_square'] = share_square

        if status:
            if mate.get('family'):
                householder = mate['family'].get('householder')
            else:
                householder = None
            if not householder:
                householder = resp_areas.get(mate['area']['_id'])
                householder = householder[0] if householder else None
            status['is_householder'] = householder == mate['_id']
            mate['summary'] = status
            if householder:
                r = result.setdefault(
                    householder,
                    {
                        'summary': {
                            'registered': 0,
                            'registered_const': 0,
                            'living': 0,
                            'ownership': 0,
                            'share_square': 0,
                        },
                        'mates': [],
                    },
                )
                if mate['_id'] == householder:
                    r['summary']['share_square'] = share_square
                r['mates'].append(mate)
                for k in _STATUSES_SUM_KEYS:
                    r['summary'][k] += status.get(k, 0)
    return result


def get_responsibles(provider_id, areas_ids, date_on, date_till=None):
    if not date_till:
        date_till = date_on
    resp = Responsibility.objects.as_pymongo().filter(
        __raw__={
            'account.area._id': {'$in': areas_ids},
            'provider': provider_id,
            '$and': [
                {
                    '$or': [
                        {'date_from': None},
                        {'date_from': {'$lt': date_till}}
                    ],
                },
                {
                    '$or': [
                        {'date_till': None},
                        {'date_till': {'$gte': date_on}}
                    ],
                },
            ],
        },
    )
    result = {}
    for r in resp:
        area_result = result.setdefault(r['account']['area']['_id'], [])
        area_result.append(r['account']['_id'])
    return result


def get_property_share(p_history, date_on, raw=False):
    for p in p_history:
        if p['value'][0] == 0 and p['value'][1] == 0:
            p['value'][1] = 1
    total_list = []
    for x in p_history:
        if x['value'] and (x.get('date') or date_on) <= date_on:
            value_to_append = (-1 if x['op'] == 'red' else 1) * Fraction(*x['value'])
            total_list.append(value_to_append)
    total = sum(total_list)
    if raw:
        return [total.numerator, total.denominator]
    return total.numerator / total.denominator
