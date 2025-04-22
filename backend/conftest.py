# -*- coding: utf-8 -*-
import pytest
import mongoengine


@pytest.fixture(scope='function')
def mongo(request):
    """Фикстура для соединения с mock базой данных."""
    db = mongoengine.connect('testdb', host='mongomock://localhost')
    yield db
    db.drop_database('testdb')
    db.close()


@pytest.fixture(scope='function', params=(
        ('8102', '8102'),
        ('+79534191515', '9534191515'),
        ('+8912000000', '912000000'),
        ('8123857300', '8123857300'),
        ('1-800-MY-APPLE', '18006927753'),
        ('8(906) 270-13-00', '9062701300'),
        ('!@#$%^&', '!@#$%^&'),
    )
)
def phone_numbers_data(request):
    """Фикстура для телефонных номеров."""
    yield request.param
