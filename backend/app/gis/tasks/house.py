from bson import ObjectId
from datetime import datetime

from app.gis.services.house_management import HouseManagement
from app.gis.workers.config import gis_celery_app


# region ОПЕРАЦИИ С ПОМЕЩЕНИЯМИ И ДОМАМИ
@gis_celery_app.task(name='gis.import_house_data')
def import_house_data(provider_id: ObjectId, house_id: ObjectId, **options):
    """
    Загрузка из ГИС ЖКХ данных дома и помещений
    """
    _export = HouseManagement.exportHouseData(
        provider_id, house_id, **options
    )
    _export()  # загружаем данные (помещений) дома операции


@gis_celery_app.task(name='gis.export_house_data')
def export_house_data(provider_id: ObjectId, house_id: ObjectId, **options):
    """
    Выгрузка в ГИС ЖКХ данных дома и помещений
    """
    HouseManagement.importHouseUOData(
        provider_id, house_id, **options
    ).binded_areas()  # обслуживаемые организацией помещения дома
# endregion ОПЕРАЦИИ С ПОМЕЩЕНИЯМИ И ДОМАМИ


# region ОПЕРАЦИИ С ВЫГРУЗКОЙ ЛИЦЕВЫХ СЧЕТОВ
@gis_celery_app.task(name='gis.import_provider_tenants')
def import_provider_tenants(
    provider_id: ObjectId, house_id: ObjectId, *tenant_id_s: ObjectId, **options
):
    """
    Загрузка из ГИС ЖКХ данных ЛС (жильцов) дома
    """
    _export = HouseManagement.exportAccountData(
        provider_id, house_id, **options
    )
    if tenant_id_s:

        _export(*tenant_id_s) # загружаем данные конкретных лицевых счетов
    else:
        _export()  # загружаем данные лицевых счетов дома


@gis_celery_app.task(name='gis.import_house_tenants')
def import_house_tenants(
    provider_id: ObjectId, house_id: ObjectId, **options
):
    """
    Загрузка из ГИС ЖКХ данных ЛС (жильцов) дома
    """
    _export = HouseManagement.exportAccountData(
        provider_id, house_id, **options
    )
    _export.house_tenants()  # загружаем данные ответственных лицевых счетов


# endregion ОПЕРАЦИИ С ВЫГРУЗКОЙ ЛИЦЕВЫХ СЧЕТОВ

# region ОПЕРАЦИИ С ЗАГРУЗКОЙ ЛИЦЕВЫХ СЧЕТОВ
@gis_celery_app.task(name='gis.export_accounts')
def export_accounts(
    provider_id: ObjectId, house_id: ObjectId, *tenant_id_s: ObjectId, **options
):
    """
    Выгрузка в ГИС ЖКХ данных определенных ЛС
    """
    if tenant_id_s and 'update_existing' not in options:
        options['update_existing'] = True  # принудительное обновление данных

    _import = HouseManagement.importAccountData(
        provider_id, house_id, **options
    )
    _import(*tenant_id_s)  # по всем направлениям платежа (начислений)


@gis_celery_app.task(name='gis.export_house_tenants')
def export_house_tenants(provider_id: ObjectId, house_id: ObjectId, **options):
    """
    Выгрузка в ГИС ЖКХ данных имеющих начисления ЛС (жильцов) дома
    """
    HouseManagement.importAccountData(
        provider_id, house_id, **options
    ).payment_accounts()  # TODO responsible_tenants()


@gis_celery_app.task(name='gis.export_period_tenants')
def export_period_tenants(provider_id: ObjectId, house_id: ObjectId,
        date_from: datetime, date_till: datetime, **options):
    """
    Выгрузка в ГИС ЖКХ данных имеющих начисления ЛС (жильцов) за период
    """
    HouseManagement.importAccountData(
        provider_id, house_id, **options
    ).period_tenants(date_from, date_till)


@gis_celery_app.task(name='gis.archive_closed_tenants')
def archive_closed_tenants(provider_id: ObjectId, house_id: ObjectId, **options):
    """
    Архивация в ГИС ЖКХ данных имеющих начисления ЛС (жильцов)
    """
    _export = HouseManagement.importAccountData(
        provider_id, house_id, **options
    ).archive_tenants()
# endregion ОПЕРАЦИИ С ЗАГРУЗКОЙ ЛИЦЕВЫХ СЧЕТОВ


# region ОПЕРАЦИИ С ПРИБОРАМИ УЧЕТА
@gis_celery_app.task(name='gis.import_provider_meters')  # TODO _house_?
def import_provider_meters(
    provider_id: ObjectId, house_id: ObjectId, **options
):
    """
    Загрузка из ГИС ЖКХ данных ПУ (помещений) дома
    """
    _export = HouseManagement.exportMeteringDeviceData(
        provider_id, house_id, **options
    )
    _export.house_meters()  # загружаем данные ПУ (помещений) дома операции


@gis_celery_app.task(name='gis.import_provider_period_meters')
def import_provider_period_meters(provider_id: ObjectId, house_id: ObjectId,
        date_from: datetime, date_till: datetime, **options):
    """
    Загрузка из ГИС ЖКХ данных ПУ (помещений) дома по периодам
    """
    _export = HouseManagement.exportMeteringDeviceData(
        provider_id, house_id, **options
    )
    _export.period_meters(date_from, date_till)  # загружаем данные ПУ (помещений) дома операции


@gis_celery_app.task(name='gis.export_provider_meters')
def export_provider_meters(
    provider_id: ObjectId, house_id: ObjectId, **options
):
    """
    Выгрузка в ГИС ЖКХ данных рабочих ПУ (помещений) дома
    """
    _import = HouseManagement.importMeteringDeviceData(
        provider_id, house_id, **options
    )
    _import.working_meters()  # только рабочие приборы учета


@gis_celery_app.task(name='gis.archive_provider_meters')
def archive_provider_meters(
    provider_id: ObjectId, house_id: ObjectId, **options
):
    """
    Выгрузка в ГИС ЖКХ данных закрытых ПУ (помещений) дома
    """
    if 'update_existing' not in options:
        options['update_existing'] = True  # принудительное обновление данных

    _import = HouseManagement.importMeteringDeviceData(
        provider_id, house_id, **options
    )
    _import.closed_meters()  # только закрытые приборы учета
# endregion ОПЕРАЦИИ С ПРИБОРАМИ УЧЕТА


if __name__ == '__main__':

    from mongoengine_connections import register_mongoengine_connections
    register_mongoengine_connections()

    p = ObjectId("5d5121792354020046c1539f")

    h = ObjectId("616fd73c62b35a00354cd85e")  # TODO в случае нескольких домов
    from app.gis.utils.houses import get_provider_house
    h = get_provider_house(p, h, abort_failed=True)

    # import_house_data(p, h); exit()
    # export_house_data(p, h); exit()  # WARN

    # import_provider_tenants(p, h); exit()
    export_house_tenants(p, h, update_existing=True); exit()  # WARN
    archive_provider_meters()
    # t = ObjectId("61e02fe7cfb10d000163c09c")
    # export_accounts(p, h, t); exit()

    # import_provider_meters(p, h); exit()
    # export_provider_meters(p, h); exit()  # WARN
