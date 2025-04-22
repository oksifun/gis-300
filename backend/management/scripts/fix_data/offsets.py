from bson import ObjectId
from app.offsets.core.run_offsets import run_house_offsets
from management.scripts.exceptions import ProviderNotFoundError, \
    HouseNotFoundError, ParameterNotFoundError
from processing.models.billing.provider.main import Provider
from processing.data_producers.associated.base import get_binded_houses_ext


def recalculate_offsets(logger, task, provider_id, house_id=None, force=''):
    """
        Функция для перерасчета задолженностей (офсетов)
        по организации (provider) или по одному указанному дому
    Args:
        logger: функция, которая пишет логи
        task: задача, запустившая скрипт
        provider_id: Id организации
        house_id: Id дома
        force:  Параметр полного обнуления офсетов до расчета новых
                True - удаляет текущие офсеты, False - мягко пересчитывает
    Returns:
        None
    """
    # Проверка на наличие параметра provider_id
    if not provider_id:
        raise ParameterNotFoundError(f'Отсутсвтует обязательный '
                                     f'параметр provider_id')
    provider_id = ObjectId(provider_id)
    provider = Provider.objects(id=provider_id).first()
    # Проверка наличия указанной организации
    if not provider:
        raise ProviderNotFoundError(f'Введен несуществующий '
                                    f'provider_id {provider_id}')
    force = True if force.lower() in ['true', '1'] else False
    logger(f'Указан параметр Force : {force}')
    if force:
        logger('Предыдущие офсеты будут удалены, будут созданы новые')
    else:
        logger('Предыдущие офсеты будут пересчитаны')
    # Получаем список домов по организации
    houses = get_binded_houses_ext(provider_id, only_active=not force)
    # Если не указан параметр house_id, перерасчет ведется по всей организации
    if not house_id:
        logger(f'Дом house_id не указан. '
               f'Перерасчет будет выполнен по всей организации.')
        # Подсчитываем количество домов в организации
        count = len(houses)
        logger(f'Всего домов по организации {count}')
        for house in houses:
            logger(f'Запускается перерасчет по дому {house}')
            run_house_offsets(provider_id, house, force=force)
        logger(f'Выполнен перерасчет '
               f'в организации {provider_id} по {count} домам')
    # Если указан параметр house_id, перерасчет ведется по указанному дому
    else:
        house_id = ObjectId(house_id)
        logger(f'Указан дом {house_id} в организации {provider_id}')
        # Проверка переданного дома на его наличие в указанной организации
        if house_id not in houses:
            raise HouseNotFoundError(f'В организации {provider_id} '
                                     f'отсутствует дом {house_id}')
        logger(f'Запускается перерасчет по дому {house_id}')
        run_house_offsets(provider_id, house_id, force=force)
        logger(f'Выполнен перерасчет '
               f'в организации {provider_id} по дому {house_id}')
