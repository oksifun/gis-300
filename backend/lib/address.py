from processing.models.billing.embeddeds.geo_point import GeoPoint
from processing.models.billing.embeddeds.location import Location
from processing.models.billing.fias import FiasHouses, Fias
from mongoengine import ValidationError, DoesNotExist, Q


class HouseValidationError(ValidationError):
    pass


def get_fias_house(fias_house_guid, raise_exception=True,
                   only_actual_houses=True):
    query = dict(HOUSEGUID=fias_house_guid)
    if only_actual_houses:
        query.update(ENDDATE__in=['2079-06-06', '9999-12-31'])
    fias_houses = FiasHouses.objects(
        **query,
    ).only(
        'HOUSENUM',
        'AOGUID',
        'BUILDNUM',
        'OKTMO',
        'STRUCNUM',
        'POSTALCODE',
        'ENDDATE',
    ).as_pymongo()
    fias_house = None
    for fias in fias_houses:
        if fias.get('ENDDATE') in ('2079-06-06', '9999-12-31'):
            return fias
        fias_house = fias
    if not fias_house and raise_exception:
        raise DoesNotExist(f'FiasHouse {fias_house_guid} is not found')
    return fias_house


def get_fias_addrobj(aoguid, raise_exception=True, only_actual_objs=True):
    query = dict(AOGUID=aoguid)
    if only_actual_objs:
        query.update(LIVESTATUS='1')
    fias_streets = Fias.objects(
        **query,
    ).only(
        'OFFNAME',
        'FORMALNAME',
        'SHORTNAME',
        'PARENTGUID',
        'AOGUID',
        'CODE',
        'POSTALCODE',
        'LIVESTATUS',
    ).as_pymongo()
    fias_street = None
    for fias in fias_streets:
        if fias.get('LIVESTATUS') == '1':
            return fias
        fias_street = fias
    if not fias_street and raise_exception:
        raise DoesNotExist(f'Fias {aoguid} is not found')
    return fias_street


def search_fias_by_address(search_str, limit=10, parent_aoguid=None,
                           only_exact_equal=False):
    query = dict(
        LIVESTATUS='1',
    )
    if parent_aoguid:
        query.update(PARENTGUID=parent_aoguid)
        hint = 'PARENTGUID_1_aolevel_1_FORMALNAME_1'
    else:
        hint = 'FORMALNAME_1'
    if ' ' in search_str or '.' in search_str or '-' in search_str:
        capitalized_str = ' '.join(
            [s.capitalize() for s in search_str.split(' ')]
        )
        capitalized_str = '.'.join(
            [s.capitalize() for s in capitalized_str.split('.')]
        )
        capitalized_str = '-'.join(
            [s.capitalize() for s in capitalized_str.split('-')]
        )
    else:
        capitalized_str = None
    if only_exact_equal:
        if capitalized_str:
            query.update(
                FORMALNAME__in=[search_str.capitalize(), capitalized_str],
            )
        else:
            query.update(
                FORMALNAME=search_str.capitalize(),
            )
        query = Q(**query)
        hint = 'FORMALNAME_1'
    else:
        if capitalized_str:
            query = (
                    Q(**query)
                    & (
                        Q(FORMALNAME__startswith=search_str.capitalize())
                        | Q(FORMALNAME__startswith=capitalized_str)
                        | Q(FORMALNAME__startswith=search_str)
                    )
            )
        else:
            query = (
                    Q(**query)
                    & (
                            Q(FORMALNAME__startswith=search_str.capitalize())
                            | Q(FORMALNAME__startswith=search_str)
                    )
            )

    data = _get_data_from_query(query, hint, limit)
    for el in data:
        path = get_fias_addrobjs_path(el['aoguid'])
        el['address'] = construct_address_from_fias_path(path)
    return data


def _get_data_from_query(query, hint, limit):
    fias_street = Fias.objects(
        query,
    ).only(
        'FORMALNAME',
        'AOGUID',
    ).order_by(
        'aolevel',
        'FORMALNAME',
    ).hint(
        hint,
    ).as_pymongo()[0: limit]
    return [
        {'aoguid': f.get('AOGUID'), 'obj': f.get('FORMALNAME')}
        for f in fias_street
    ]


def get_fias_addrobjs_path(street_aoguid=None, street_fias=None):
    if not street_fias:
        street_fias = get_fias_addrobj(street_aoguid)
    path = [street_fias]
    if not(street_fias.get('PARENTGUID')):
        return path
    next_parent = get_fias_addrobj(street_fias['PARENTGUID'])
    path.insert(0, next_parent)
    while next_parent.get('PARENTGUID'):
        next_parent = get_fias_addrobj(next_parent['PARENTGUID'])
        path.insert(0, next_parent)
    return path


def construct_address_from_fias_path(fias_addrobjs_path):
    return ', '.join(
        el['SHORTNAME'] + ' ' + el['FORMALNAME']
        for el in fias_addrobjs_path
    )


def get_street_location_by_fias(fias_street_guid, number=None, bulk=None,
                                receive_geo_point=True):
    fias_street = get_fias_addrobj(
        fias_street_guid,
        only_actual_objs=True,
    )

    fias_addrobjs_path = get_fias_addrobjs_path(fias_street['AOGUID'])
    street = construct_address_from_fias_path(fias_addrobjs_path)
    fias_addrobjs = [el['AOGUID'] for el in fias_addrobjs_path]
    street_only = f"{fias_street['SHORTNAME']} {fias_street['FORMALNAME']}"
    if receive_geo_point:
        geo_point = GeoPoint.create_by_address_str(street_only)
    else:
        geo_point = None
    return Location(
        location=street,
        fias_house_guid=None,
        fias_street_guid=fias_street['AOGUID'],
        fias_addrobjs=fias_addrobjs,

        house_number=None,
        area_number=None,
        postal_code=None,

        point=geo_point,

        extra={
            'address': street,
            'address_full': construct_address(
                house_address=street,
                postal_code=None,
                area_number=None,
            ),
            'street_only': street_only,
            'kladr': fias_street.get('CODE') or '',
            'oktmo': None,
            'house_number': number,
            'bulk': bulk,
            'structure_num': None,
        },
    )


def get_location_by_fias(fias_house_guid, area_number=None,
                         receive_geo_point=True):
    fias_house = get_fias_house(
        fias_house_guid,
        only_actual_houses=False,
    )
    fias_street = get_fias_addrobj(
        fias_house['AOGUID'],
        only_actual_objs=True,
    )
    fias_addrobjs_path = get_fias_addrobjs_path(fias_street['AOGUID'])

    street = construct_address_from_fias_path(fias_addrobjs_path)
    fias_addrobjs = [el['AOGUID'] for el in fias_addrobjs_path]
    street_only = f"{fias_street['SHORTNAME']} {fias_street['FORMALNAME']}"
    house_number = construct_house_number(
        fias_house.get('HOUSENUM'),
        bulk=fias_house.get('BUILDNUM'),
        structure_num=fias_house.get('STRUCNUM'),
    )
    address = construct_house_address(
        street,
        house_number_full=house_number,
    )
    if receive_geo_point:
        geo_point = GeoPoint.create_by_address_str(address)
    else:
        geo_point = None
    postal_code = (
            fias_house.get('POSTALCODE')
            or fias_street.get('POSTALCODE')
            or None
    )
    return Location(
        location=street,
        fias_house_guid=fias_house_guid,
        fias_street_guid=fias_street['AOGUID'],
        fias_addrobjs=fias_addrobjs,

        house_number=house_number,
        area_number=area_number,
        postal_code=postal_code,

        point=geo_point,

        extra={
            'address': address,
            'address_full': construct_address(
                house_address=address,
                postal_code=postal_code,
                area_number=area_number,
            ),
            'street_only': street_only,
            'kladr': fias_street.get('CODE') or '',
            'oktmo': fias_house.get('OKTMO') or '',
            'house_number': fias_house.get('HOUSENUM'),
            'bulk': fias_house.get('BUILDNUM'),
            'structure_num': fias_house.get('STRUCNUM'),
        },
    )


def construct_house_number(number, bulk=None, structure_num=None):
    short_address = f"{number}"
    if bulk:
        short_address += f" корп. {bulk}"
    if not structure_num:
        return short_address
    if structure_num.isalpha():
        short_address += f" лит. {structure_num}"
    elif structure_num.isnumeric():
        short_address += f" стр. {structure_num}"
    return short_address


def construct_house_address(street_address, house_number_full=None,
                            house_number=None, bulk=None, structure_num=None):
    if not house_number_full:
        house_number_full = construct_house_number(
            house_number or '',
            bulk=bulk,
            structure_num=structure_num,
        )
    return f"{street_address}, д. {house_number_full}"


def construct_address(house_address=None,
                      street_address=None,
                      house_number_full=None,
                      house_number=None, bulk=None, structure_num=None,
                      postal_code=None, area_number=None):
    if not house_address:
        house_address = construct_house_address(
            street_address or '',
            house_number_full=house_number_full,
            house_number=house_number,
            bulk=bulk,
            structure_num=structure_num,
        )
    if postal_code:
        address = f"{postal_code}, {house_address}"
    else:
        address = house_address
    if area_number:
        address += f', пом. {area_number}'
    return address


def get_address_by_fias(fias_house_guid, street_address,
                        postal_code=None, area_number=None):
    fias = get_fias_house(fias_house_guid)
    return construct_address(
        street_address=street_address,
        house_number=fias.get('HOUSENUM'),
        bulk=fias.get('BUILDNUM'),
        structure_num=fias.get('STRUCNUM'),
        postal_code=postal_code,
        area_number=area_number,
    )
