from bson import ObjectId

from app.area.models.area import Area
from app.meters.models.meter import AreaMeter
from processing.models.billing.account import Tenant
from processing.models.logging.custom_scripts import CustomScriptData


def clean_area_communications(logger, task, area_id):
    """
    Удаляет из квартиры вводы коммунальных услуг, на которых нет ни одного
    счётчика. При этом контролируется наличие хотя бы одного ввода обязательного
    типа

    :param logger: функция, которая пишет логи
    :param task: задача, запустившая скрипт
    :param area_id: помещение
    :return:
    """
    area_id = ObjectId(area_id)
    area = Area.objects(pk=area_id).get()
    CustomScriptData(
        task=task.id if task else None,
        coll='Meter',
        data=[area.to_mongo()]
    ).save()
    logger('Вводов в помещении {}'.format(len(area.communications)))
    used_communications = AreaMeter.objects(
        area__id=area_id
    ).as_pymongo().distinct('communication')
    logger('Вводов счётчиков {}'.format(len(used_communications)))
    # сосотавляем список только используемых вводов
    area_communications = \
        [c for c in area.communications if c.id in used_communications]
    # проверяем, что есть хотя бы один ввод обязательных типов
    for c_type in ('cold_water', 'hot_water', 'electricity', 'heat'):
        if not [c for c in area_communications if c['meter_type'] == c_type]:
            for comm in area.communications:
                if comm['meter_type'] == c_type:
                    area_communications.append(comm)
                    break
    area.communications = area_communications
    area.save()
    logger('Оставила {}'.format(len(area.communications)))


def repair_householders(logger, task, area_id):
    """
    Исправляет ошибочные ссылки жителей друг на друга

    :param logger: функция, которая пишет логи
    :param task: задача, запустившая скрипт
    :param area_id: помещение
    :return:
    """
    area = ObjectId(area_id)
    tenants = Tenant.objects(area__id=area)
    CustomScriptData(
        task=task.id if task else None,
        coll='Account',
        data=list(tenants.as_pymongo()),
    ).save()
    logger('Жителей в помещении {}'.format(tenants.count()))
    householders = [
        tenant.id
        for tenant in tenants
        if (
                tenant.family
                and tenant.family.householder == tenant.id
        )
    ]
    logger('Семей в помещении {}'.format(tenants.count()))
    updated = 0
    for tenant in tenants:
        if tenant.family and tenant.family.householder not in householders:
            error_householder = [
                i for i in tenants
                if i.id == tenant.family.householder
            ][0]
            if (
                    error_householder.family
                    and error_householder.family.householder in householders
            ):
                correct_householder = error_householder.family.householder
                tenant.family.householder = correct_householder
                tenant.save()
                updated += 1
    logger(f'Исправлено {updated}')
    # рекурсия для повтороного прохождения по списку из жителей
    # потому что householder мог примениться не ко всем
    if not all(
            tenant.family.householder in householders
            for tenant in tenants
            if tenant.family and tenant.family.householder
    ):
        repair_householders(logger, task, area_id)
