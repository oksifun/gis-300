# -*- coding: utf-8 -*-
from bson import ObjectId


def sanitize_string(string: str) -> str:
    """Удаляет символы !@#$%., из строки."""
    table = string.maketrans('', '', '!@#$%.,')
    return string.translate(table)


def transform_objectid_to_str(d):
    """Преобразовывает все ObjectId к строке."""
    if isinstance(d, ObjectId):
        return str(d)

    if isinstance(d, list):
        return [transform_objectid_to_str(x) for x in d]

    if isinstance(d, dict):
        for k, v in d.items():
            d.update({k: transform_objectid_to_str(v)})
    return d
