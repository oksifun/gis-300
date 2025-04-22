import datetime

from typing import (
    Union,
    List,
    Dict,
)

from bson import ObjectId

from app.house.models.house import House

from processing.models.billing.provider.main import Provider
from processing.models.billing.business_type import BusinessType
from processing.models.billing.base import BindsPermissions


def get_contracting_providers_for_request(
        binds: Union[BindsPermissions, dict]
) -> List[Dict[ObjectId, str]]:
    """
    Получение списка провайдеров подрядных организаций для заданных биндов.

    Args:
        binds: Привязки, для которых нужно получить список провайдеров.

    Returns:
        Список словарей с информацией (id, str_name) о подрядных организациях.

    """
    houses = House.objects(
        House.get_binds_query(binds),
    ).only(
        'service_binds',
    ).as_pymongo()
    if not houses:
        return []
    date = datetime.datetime.now()
    business_types = get_request_business_types()
    providers = set()
    for house in houses:
        if house.get('service_binds'):
            for bind in house['service_binds']:
                if (
                        bind.get('provider')
                        and bind.get('is_active')
                        and bind.get('is_public')
                        and ((bind.get('date_start') or date) <= date)
                        and ((bind.get('date_end') or date) >= date)
                        and (bind.get('business_type') in business_types)
                ):
                    providers.add(bind['provider'])
    providers = Provider.objects(
        id__in=list(providers),
    ).only(
        'str_name',
    ).as_pymongo()
    return sorted(list(providers), key=lambda x: x['str_name'])


def get_request_business_types() -> List[ObjectId]:
    """
    Получение списка видов деятельности организации для запросов.

    Returns:
        Список с идентификаторами видов деятельности.

    """
    b_types = BusinessType.objects(
        slug__nin=['pbg', 'gvs', 'hvs', 'pel', 'otd', 'gov'],
    ).distinct(
        '_id',
    )
    return b_types
