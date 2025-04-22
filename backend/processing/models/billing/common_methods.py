from bson import ObjectId

from processing.models.billing.house_group import HouseGroup
from processing.models.billing.area_bind import AreaBind

from processing.models.choices import AreaType


def get_ranges(*numbers: int):  # -> generator
    """Получить диапазон(ы) из списка чисел"""
    from itertools import groupby

    sorted_numbers: list = sorted(numbers)

    for index, grouper in groupby(enumerate(sorted_numbers),
            lambda pair: pair[1] - pair[0]):
        group = list(grouper)  # : itertools._grouper = <(0,1), (1,2), (2,3)>
        yield group[0][1], group[-1][1]


def get_areas_range(house_id: ObjectId, provider_id: ObjectId) -> str:
    """Диапазон(ы) помещений дома"""
    from app.area.models.area import Area

    binded_area_ids: list = AreaBind.objects(__raw__={
        'provider': provider_id,  # индекс
        'closed': None,
    }).distinct('area')
    if not binded_area_ids:
        return ''

    grouped_numbers: dict = {  # TODO OrderedDict?
        AreaType.LIVING_AREA: set(),
        AreaType.NOT_LIVING_AREA: set(),
        AreaType.PARKING_AREA: set(),
    }  # WARN устанавливаем порядок диапазонов номеров по типам помещений
    for area in Area.objects(__raw__={
        '_id': {'$in': binded_area_ids},
        'house._id': house_id,  # индекс
        'is_deleted': {'$ne': True},
    }).only(
        '_type', 'number'
    ).as_pymongo():
        assert area['_type'] and area['_type'][0] in {AreaType.LIVING_AREA,
            AreaType.NOT_LIVING_AREA, AreaType.PARKING_AREA}
        grouped_numbers[area['_type'][0]].add(area['number'])

    areas_range: list = []
    for kind, numbers in grouped_numbers.items():
        if not numbers:  # нет помещений вида?
            continue  # пропускаем вид
        suffix: str = Area.suffix_of(kind)
        for _range in get_ranges(*numbers):  # : tuple
            if _range[0] == _range[1]:  # отдельный элемент?
                areas_range.append(f"{_range[0]}{suffix}")
            else:  # последовательность элементов!
                areas_range.append(f"{_range[0]}{suffix}-{_range[1]}{suffix}")

    return ', '.join(areas_range)  # '' для пустого списка


def get_area_house_groups(area_id: ObjectId, house_id: ObjectId) -> list:
    """
    Возвращает список групп домов, к которым принадлежит помещение
    """
    # ищем провайдеров, с которыми есть привязка
    providers = [
        x['provider']
        for x in AreaBind.objects(
            area=area_id,
            closed=None,
        ).only('provider').as_pymongo()
    ]
    if not providers:
        return []
    # отдаём группы домов
    return HouseGroup.objects(
        provider__in=providers,
        houses=house_id
    ).distinct('id')


def get_house_groups(house_id: ObjectId) -> list:
    """
    Возвращает список групп домов, к которым принадлежит дом
    """
    return HouseGroup.objects(houses=house_id).distinct('id')


def get_area_number(description: str) -> tuple:
    """
    1. Вырезаем лишние пробелы (двойные и окаймляющие):
    ' пом. 12 офис  Н ' -> 'пом. 12 офис  Н'  (перед Н 2 пробела)

    2. Анализируем, если номер заканчивается на ' Н' или ' П',
    то удаляем пробелы до тех пор, пока ' Н' и ' П' перестанет находится:
    'пом. 12 офис  Н' -> 'пом. 12 офисН'

    3. Удаляем все НЕ цифры с первого символа до первой цифры:
    'пом. 12 офисН' -> '12 офисН'

    4. Формируем number из последовательного перебора с первого символа
    до последнего цифрового:
    '12 офисН' -> number: 12

    5. Удаляем из него символы с первого по длину number.
    '12 офисН' -> ' офисН'

    6. Анализируем, если последний символ Н или П, то
    присваиваем помещению тип "Нежилое" или "Паркинг" соответственно,
    а последний символ удаляем.
    ' офисН' -> ' офис', _type: 'not_living'

    7. Обрезаем пробелы с обеих сторон:
    ' офис' -> 'офис'

    8. Если длина равна 1 символу, то присваиваем ее значение
    в num_letter (литера).

    9. Если первый символ - '/', то удаляем первый символ
    и присваиваем остаток в num_alt.

    10. Записываем остаток в num_desc.
    """
    if not description:  # описание отсутствует?
        return ()

    pattern = r'[\s(]*(?:([а-яa-z\s\\/\.]*?)\s*)?\W*(\d+)' \
              r'(?:[\s\\/()-]+(\d+))?\W*(\w+)?\W*([НП])?[\s)]*'

    from re import search, IGNORECASE
    match = search(pattern, description, IGNORECASE)  # или None

    # WARN ('префикс', 'номер', 'доп.номер', 'суффикс', 'вид')
    return match.groups() if match is not None else ()
