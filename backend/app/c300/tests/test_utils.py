# -*- coding: utf-8 -*-
from bson import ObjectId
from datetime import date
import pytest

from app.c300.utils.strings import (
    sanitize_string,
    transform_objectid_to_str,
)

test_data_for_sanitize_string = (
    ('!!! ALERT !!!', ' ALERT '),
    ('Мама мыла раму', 'Мама мыла раму'),
    ('!?', '?'),
    ('г. Санкт-Петербург, ул. Ленина, дом 23/2',
     'г Санкт-Петербург ул Ленина дом 23/2'),
)


test_data_for_transform_objectid_to_str = (
    (ObjectId('5ecf8358002a910001fecad7'), '5ecf8358002a910001fecad7'),
    (
        [ObjectId('5ecf8358002a910001fecad7'), 1456, 'qwerty'],
        ['5ecf8358002a910001fecad7', 1456, 'qwerty'],
    ),
    (
        {
            '_id': ObjectId('5ecf8358002a910001fecad7'),
            'city': 'Chelyabinsk',
            'founded_at': date(1736, 1, 1),
        },
{
            '_id': '5ecf8358002a910001fecad7',
            'city': 'Chelyabinsk',
            'founded_at': date(1736, 1, 1),
        }
    ),
)


@pytest.mark.parametrize(
    'string, result',
    test_data_for_sanitize_string,
)
def test_sanitize_string(string, result):
    assert sanitize_string(string) == result


@pytest.mark.parametrize(
    'container, result',
    test_data_for_transform_objectid_to_str,
)
def test_transform_objectid_to_str(container, result):
    assert transform_objectid_to_str(container) == result