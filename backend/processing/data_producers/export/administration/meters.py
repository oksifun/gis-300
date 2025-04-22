import datetime

from app.area.models.area import Area
from app.meters.models.meter import AreaMeter
from processing.data_producers.associated.base import get_binded_houses
from app.house.models.house import House
from processing.models.billing.provider.main import Provider
from utils.crm_utils import get_crm_client_ids


def get_automatic_meters_count(logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    title_row = [
        'ИНН',
        'Наименование',
        'Адрес',
        'количество ипу',
        'количество квартир',
        'марки',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    date = datetime.datetime.now()
    for provider_id in clients_ids:
        provider = Provider.objects(
            pk=provider_id,
        ).only(
            'id',
            'inn',
            'str_name',
        ).as_pymongo().get()
        houses = get_binded_houses(provider_id)
        for house in houses:
            meters = AreaMeter.objects(
                __raw__={
                    'area.house._id': house,
                    'is_automatic': True,
                    '_type': 'HeatAreaMeter',
                    'is_deleted': {'$ne': True},
                    'working_start_date': {'$lte': date},
                    '$or': [
                        {'working_finish_date': {'$gte': date}},
                        {'working_finish_date': None},
                    ],
                },
            )
            h = House.objects(pk=house).only('address').as_pymongo().get()
            count = meters.count()
            if not meters:
                continue
            brands = meters.distinct('brand_name')
            areas = Area.objects(
                house__id=house,
                is_deleted__ne=True,
            ).count()
            if '' in brands:
                brands.remove('')
            if None in brands:
                brands.remove(None)
            row = [
                provider['inn'],
                provider['str_name'],
                h['address'],
                str(count),
                str(areas),
                ', '.join(brands),
            ]
            result.append(row)
            if table_print:
                table_print(
                    ';'.join(row)
                )
    return result
