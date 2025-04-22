from bson import ObjectId

from app.house.models.house import House
from processing.models.logging.custom_scripts import CustomScriptData


def make_provider_public(logger, task, provider_id, address_search_string=None):
    """
    Скрипт проставляет статус "Публичная организация" заданным объектам
    можно указать адрес или часть его для уточнения поиска.
    :param logger: функция, которая пишет логи
    :param task: задача, запустившая скрипт
    :param provider_id: провайдер, указанный в привязках дома
    :param address_search_string: строка поиска по адресу
    """
    houses = House.objects(service_binds__provider=ObjectId(provider_id))
    if address_search_string:
        houses = houses.filter(address__icontains=address_search_string)
    CustomScriptData(
        task=task.id if task else None,
        coll='House',
        data=list(houses.as_pymongo()),
    ).save()
    houses.update(
        set__service_binds__S__is_public=True,
    )
    logger(f'Обновлено домов {houses.count()}')
