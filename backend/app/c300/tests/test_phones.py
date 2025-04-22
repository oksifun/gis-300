# -*- coding: utf-8 -*-
from app.c300.utils.phones import only_national_number


def test_only_national_number(phone_numbers_data):
    assert only_national_number(phone_numbers_data[0]) == phone_numbers_data[1]
