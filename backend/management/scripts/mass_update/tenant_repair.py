from bson import ObjectId

from processing.models.billing.account import Tenant


def undo_remove_tenants(logger, task, area):
    """
    Скрипт восстанавливает жильцов в квартире по переданному id
    :param logger: функция, которая пишет логи
    :param task: задача, запустившая скрипт
    :param area: id квартиры в которой нужно восстановить жителей
    :return:
    """
    try:
        area = ObjectId(area)
    except Exception as error:
        return logger(f'Не верный id квартиры, ошибка: {error}')

    Tenant.objects(area__id=area, is_deleted=True,).update(is_deleted=False)
    return logger(f'Все жители восстановлены')


if __name__ == "__main__":
    from mongoengine_connections import register_mongoengine_connections
    register_mongoengine_connections()
    logger = print
    task = None
    area_id = '5d8b65e2f06bc20001dda8f2'
    repair_tenants(logger, task, area_id)
