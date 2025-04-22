from app.accruals.cipca.source_data.areas import \
    get_areas_calculation_data, get_mates
from app.accruals.cipca.source_data.meters import get_meters
from processing.models.billing.account import Tenant


_TENANT_FIELDS = (
    'area',
    'last_name',
    'first_name',
    'patronymic_name',
    'name',
    'str_name',
    'short_name',
    'number',
    'statuses',
    'family',
    'rooms',
    'privileges',
    'coefs',
    'email',
    'phones',
)


def get_overall_calculation_data(provider_id, house_id, month, accounts_ids,
                                 readings_month):
    # получаем искомых жителей
    if len(accounts_ids) < 10 or not house_id:
        accounts = Tenant.objects(
            pk__in=accounts_ids,
        ).only(
            *_TENANT_FIELDS,
        ).as_pymongo()
    else:
        accounts = Tenant.objects(
            __raw__={
                'area.house._id': house_id,
            },
        ).only(
            *_TENANT_FIELDS,
        ).as_pymongo()
        accounts = [a for a in accounts if a['_id'] in accounts_ids]
    # получаем их квартиры
    areas = get_areas_calculation_data(
        month,
        [a['area']['_id'] for a in accounts],
    )
    # получаем сожителей
    mates = get_mates(month, provider_id, areas)
    # получаем счётчики
    meters = get_meters(areas.values(), readings_month)
    # компонуем всё
    result = {}
    for account in accounts:
        data = result.setdefault(account['_id'], {})
        data['account'] = account
        data['area'] = areas[account['area']['_id']]
        data['mates'] = mates.get(account['_id'], [])
        data['meters'] = meters.get(account['area']['_id'], [])
    return result
