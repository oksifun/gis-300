from app.house.models.house import House
from processing.models.billing.fias import Fias


def get_all_provider_binded_houses_ids(provider_id):
    """
    Получение id домов, когда-либо бывших привязанными к организации
    """
    all_houses = House.objects(
        service_binds__provider=provider_id
    ).as_pymongo().only('id')
    return set(house['_id'] for house in all_houses)


def _get_sectors(bind):
    """
    Получение sector_code домов, привязанных к организации переданной в функции
                                                    get_providers_binded_houses
    """
    if not bind.get('sectors'):
        return []
    return [x['sector_code'] for x in bind['sectors']]


def get_providers_binded_houses(provider_id, date_on, ignat=False):
    """
    Получение домов, привязанных к переданной организации
    :return:
    """

    fields = [
        'id',
        'address',
        'fias_street_guid',
        'service_binds.provider',
        'service_binds.sectors',
        'service_binds.is_active',
        'service_binds.date_start',
        'service_binds.date_end',
    ]
    if ignat:
        fields = [
            'service_binds',
            'id',
            'address',
            'fias_street_guid',
        ]
    all_houses = House.objects(
        service_binds__provider=provider_id
    ).as_pymongo().only(*fields)
    region_codes = _get_region_code(
        list({x['fias_street_guid'] for x in all_houses})
    )
    houses = [
        dict(
            house_id=str(house['_id']),
            address=house['address'],
            bind_state=_get_bind_state(bind, date_on),
            sectors=_get_sectors(bind),
            region_code=region_codes.get((house['fias_street_guid'])),
            service_binds=house['service_binds']

        )
        for house in all_houses._iter_results()
        for bind in house['service_binds']
        if bind['provider'] == provider_id
    ]
    return houses


def _get_bind_state(bind, date):
    """ Определение состояния активности привязки на данный момент """
    date_condition = (
            (bind.get('date_start') or date)
            <= date
            <= (bind.get('date_end') or date)
    )
    if bind['is_active'] and date_condition:
        bind_state = True
    else:
        bind_state = False
    return bind_state


def _get_region_code(aoguids):
    """Поиск кодов регионов по кодам ФИАС"""
    codes = Fias.objects(
        AOGUID__in=aoguids
    ).as_pymongo().only('AOGUID', 'REGIONCODE')
    return {x['AOGUID']: x['REGIONCODE'] for x in codes}
