from bson import ObjectId

from app.gis.services.nsi import Nsi
from app.gis.services.nsi_common import NsiCommon

from app.gis.utils.nsi import get_list_group, get_item_name, \
    NSI_GROUP, NSIRAO_GROUP, PAGED_NSI
from app.gis.workers.config import gis_celery_app


@gis_celery_app.task(name='gis.import_group_nsi', ignore_result=True)
def import_group_nsi(group_name: str, start_from: int = 0, **options):
    """
    Загрузка из ГИС ЖКХ группы общих справочников

    :param group_name: 'NSI' или 'NSIRAO'
    :param start_from: номер справочника с которого начнется загрузка (исключ.)
    """
    nsi_reg_nums = [*NSI_GROUP] if group_name == 'NSI' else [*NSIRAO_GROUP]

    nsi_reg_nums.sort(key=lambda num: num)  # сортируем справочники по номерам
    limited_reg_nums: list = [num for num in nsi_reg_nums if num > start_from]

    import_common_nsi(limited_reg_nums, **options)


@gis_celery_app.task(name='gis.import_common_nsi', ignore_result=True)
def import_common_nsi(registry_numbers: list, **options):
    """
    Загрузка из ГИС ЖКХ (определенных) общих справочников

    :param registry_numbers: номера общих справочников для загрузки
    """
    assert registry_numbers, "Для загрузки необходимы номера справочников"

    for registry_number in registry_numbers or [*NSI_GROUP, *NSIRAO_GROUP]:
        list_group: str = get_list_group(registry_number)  # группа
        item_name: str = get_item_name(registry_number)  # название

        if registry_number in PAGED_NSI:  # постраничная выгрузка? (70, 196)
            _export = NsiCommon.exportNsiPagingItem(**options)

            _export.log(info=f"Загружается первая страница общего"
                f" справочника №{registry_number}: «{item_name}»")

            _export(Page=1,  # Обязательное! Минимум = 1
                ListGroup=list_group, RegistryNumber=registry_number)
        else:  # стандартная (не постраничная) выгрузка!
            _export = NsiCommon.exportNsiItem(**options)

            _export.log(info="Загружаются элементы общего справочника"
                f" №{registry_number}: «{item_name}»")

            _export(ListGroup=list_group, RegistryNumber=registry_number)


@gis_celery_app.task(name='gis.import_provider_nsi')
def import_provider_nsi(provider_id: ObjectId, registry_number: int, **options):
    """
    Загрузка из ГИС ЖКХ (определенных) частных справочников организации
    """
    Nsi.exportDataProviderNsiItem(
        provider_id, **options
    ).by_reg_num(registry_number)


@gis_celery_app.task(name='gis.export_additional_services')
def export_additional_services(provider_id: ObjectId, **options):
    """
    Выгрузка в ГИС ЖКХ справочника дополнительных услуг организации
    """
    Nsi.importAdditionalServices(
        provider_id, **options
    ).actual()  # только актуальные Дополнительные услуги


@gis_celery_app.task(name='gis.export_municipal_services')
def export_municipal_services(provider_id: ObjectId, **options):
    """
    Выгрузка в ГИС ЖКХ справочника коммунальных услуг организации
    """
    Nsi.importMunicipalServices(
        provider_id, **options
    ).actual()  # только актуальные Коммунальные услуги


@gis_celery_app.task(name='gis.export_municipal_resources')
def export_municipal_resources(provider_id: ObjectId, **options):
    """
    Выгрузка в ГИС ЖКХ справочник коммунальных ресурсов на ОДН организации
    """
    Nsi.importGeneralNeedsMunicipalResource(
        provider_id, **options
    ).actual()  # только актуальные КР на ОДН


if __name__ == '__main__':

    # import_group_nsi('NSI'); exit()  # группа общих
    # import_common_nsi([
    #     3, 50,  # услуги
    #     2,  # Вид коммунального ресурса
    #     16,  # Межповерочный интервал
    #     21,  # Причина архивации ПУ
    #     22,  # Причина закрытия ЛС
    #     24,  # Состояние дома
    #     27,  # Тип прибора учета
    #     30,  # Характеристика помещения
    #     32,  # Часовые зоны по Olson
    #     197,  # данные ожф
    #     329,  # Неустойки и судебные расходы
    #     338,  # стадия жизненного цикла дома
    #     # 70,  # многостраничный
    # ]); exit()  # общие

    from mongoengine_connections import register_mongoengine_connections
    register_mongoengine_connections()

    p = ObjectId('5fc63bbce04bde00012eef7e')

    import_provider_nsi(p, 1)
    import_provider_nsi(p, 51)
    import_provider_nsi(p, 337); exit()

    # Nsi.exportDataProviderNsiItem(p).private_services(); exit()

    # export_additional_services(p); exit()  # WARN
    # export_municipal_services(p); exit()  # WARN
    # export_municipal_resources(p); exit()  # WARN
