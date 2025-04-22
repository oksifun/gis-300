# -*- coding: utf-8 -*-
import pytest

from app.c300.utils.strings import sanitize_string


test_data_for_sanitize_string = (
    ('!!! ALERT !!!', ' ALERT '),
    ('Мама мыла раму', 'Мама мыла раму'),
    ('!?', '?'),
    ('г. Санкт-Петербург, ул. Ленина, дом 23/2',
     'г Санкт-Петербург ул Ленина дом 23/2'),
    ('/home/user/', '/home/user/'),
    (r'C:\Windows\Installer', r'C:\Windows\Installer'),
)


@pytest.mark.parametrize(
    'string, result',
    test_data_for_sanitize_string,
)
def test_sanitize_string(string, result):
    assert sanitize_string(string) == result
