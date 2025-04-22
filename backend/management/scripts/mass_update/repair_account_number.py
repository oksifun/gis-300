from bson import ObjectId

from app.house.models.house import House
from processing.data_producers.associated.base import get_binded_houses
from processing.models.billing.account import Tenant
from processing.models.billing.fias import Fias


def start_repair_account_number(logger, task, provider):
    """
    Функция собирает все дома принажлежащие провайдеру, затем
    по каждому дому  дому ищет фиасе  REGIONCODE и составляет словарь с
    отношением id-дома: код региона. Затем пробегает по всем жителям живущих
    в домах принажлежащих провайдеру и меняет личный номер  на новый верный!
    В зависимости в каком доме живет Tenant проставляется REGIONCODE

    :param provider: id организации в которой есть плохие личные счета
    """

    try:
        provider = ObjectId(provider)
    except Exception as error:
        logger('Параметр организации передан неверно!')
        return

    logger('Запущен скрипт исправления личного номера')
    houses_id = get_binded_houses(provider)
    houses = House.objects(
        id__in=houses_id
    ).as_pymongo().only('id', 'fias_addrobjs')
    fiases = Fias.objects(
        AOGUID__in=[i['fias_addrobjs'][0] for i in houses]
    ).as_pymongo().only('AOGUID', 'REGIONCODE')
    house_region_code = {}
    for house in houses:
        for fias in fiases:
            if fias['AOGUID'] in house['fias_addrobjs']:
                house_region_code[house['_id']] = fias['REGIONCODE']
                continue
    tenants = Tenant.objects(
        _type="PrivateTenant",
        area__house__id__in=houses_id,
    )
    count = tenants.count()
    progress = 0
    for tenant in tenants:
        if tenant.number[0:2] != house_region_code[tenant.area.house.id]:
            tenant.old_numbers.append(tenant.number)
            tenant.number = ''
            tenant.save()
        progress += 1
        logger(f'Завершено на {round((progress * 100 / count), 2)}')


if __name__ == '__main__':
    from mongoengine_connections import register_mongoengine_connections
    register_mongoengine_connections()
    start_repair_account_number(print, None, '526234b3e0e34c4743822066')
