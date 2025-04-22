from app.area.models.area import Area
from processing.models.billing.account import Tenant
from app.house.models.house import House
from app.accruals.models.accrual_document import AccrualDoc
from processing.models.logging.custom_scripts import CustomScriptData

from scripts.data_move.areas import move_areas
from scripts.migrations.split_accruals.accrual_doc_split import \
    split_accrual_doc
from scripts.migrations.reversal import split_reversal_doc


def split_house(
        logger, task, provider_id,
        house_from_id, house_to_id, numbers, liter='', bulk='',
        clean_house=False):
    """
    Фукция для разделения дома. принимает id дома который нужно разделить и
    id дома цели. А так же строку с перечислением номеров квартир вида :
    1, 2, 3, 4-25, 1Н, 4Н, 10Н-40Н
    Номера квартир должны указываться через запятую, диапазон задается дефисом
    между от начального значения квартиры до конечного. Нежелые и прочие
    помещения обозначаются литерой на конце. Диапазон задается так же как и у
    числовых квартир.
    :param house_from_id: id дома родителя
    :param house_to_id: id дома цели
    :param numbers: строка с номерами квартир
    :param liter: Литер для дома если нужно сменить
    :param clean_house: если нужно очистить дом цель, то отправить  True,
    иначе False, по умолчанию False
    """
    areas_numbers = _numbers_validation(numbers)
    house = House.objects(id=house_to_id).first()
    if not house:
        logger('Дома не существует!')
        return
    house.structure = liter if liter else house.structure
    house.bulk = bulk if bulk else house.bulk
    house.save()
    # Отчистка дома от квартир внутри него, если это неободимо
    if clean_house:
        _clean_house(house.id)
    # Обновление квартир
    logger("Обновление квартир")
    areas_query = Area.objects(
        house__id=house_from_id,
        str_number__in=areas_numbers,
    )
    CustomScriptData(
        task=task.id if task else None,
        coll='Area',
        data=list(areas_query.as_pymongo()),
    ).save()
    areas_ids = areas_query.distinct('id')
    move_areas(areas_query, house)
    # Обновление акрул доков
    logger("Обновление акрул доков")
    accrual_docs = AccrualDoc.objects(house__id=house_from_id).as_pymongo()
    accounts = Tenant.objects(area__id__in=areas_ids).distinct('id')
    for accrual_doc in accrual_docs:
        split_accrual_doc(False, accrual_doc['_id'], house.id, accounts)

    # Обновление Reversal
    logger("Обновление Reversal")
    split_reversal_doc(False, house.id)


def _clean_house(id_house):
    Area.objects(house__id=id_house).delete()


def _numbers_validation(numbers):
    """
    Функция парсинга строки с номерами квартир
    """
    areas = []
    numbers_list = numbers.split(',')
    for i in numbers_list:
        i = i.strip()
        if '-' in i and not i[-1].isalpha():
            areas.extend(get_ful_range_areas(i))
        if i.isdigit():
            areas.append(i)
        if i[-1].isalpha() and '-' in i:
            str_range = i.replace(i[-1], '')
            areas.extend(get_ful_range_areas(str_range, i[-1]))
        if i[-1].isalpha() and i[:-1].isdigit():
            areas.append(i)
    return areas


def get_ful_range_areas(areas_str, liter=''):
    areas_str = areas_str.split('-')
    first_area = (int(areas_str[0].strip()))
    last_area = (int(areas_str[1].strip()) + 1)
    return list(map(
        lambda i: f'{i}{liter}', list(range(first_area, last_area))
    ))


if __name__ == "__main__":
    from mongoengine_connections import register_mongoengine_connections
    register_mongoengine_connections()
    numbers = '1-100'
    split_house(
        "52f375cdb6e6971b90332fb8",
        "5315899fb6e6975598d0d863",
        numbers,
        liter='',
        bulk='7',
        clean_house=True,
    )
