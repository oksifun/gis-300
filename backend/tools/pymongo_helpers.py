from datetime import datetime, date
from decimal import Decimal


def fix_fields_for_pymongo(item):
    """
    Pymongo не поддержавает сохранение следующих типов:
        datetime.date
        decimal.Decimal

    Данный метод рекурсивно обрабатывает объект(словарь, список или дата),
    и заменяет объекты datetime.date на datetime.datetime
    :param item:
    :return:
    """
    if isinstance(item, list):
        return [
            fix_fields_for_pymongo(sub_el)
            for sub_el in item
        ]

    elif isinstance(item, dict):
        return {
            key: fix_fields_for_pymongo(sub_el)
            for key, sub_el in item.items()
        }

    elif isinstance(item, date):
        return datetime.combine(item, datetime.min.time())

    elif isinstance(item, Decimal):
        # TODO Убрать после полного перехода на PyMongo 3.4
        # PyMongo >= 3.4 supports the Decimal128 BSON type
        # introduced in MongoDB 3.4.
        return float(item)

    else:
        return item

