# -*- coding: utf-8 -*-
import pytest

from processing.models.billing.base import BindsPermissions
from mongoengine.errors import ValidationError


def test_serialized_binds():
    binds = {
        'pr': '526234b2e0e34c4743821ee2',
        'hg': '5bae4ae34eb94d002d99c8d4',
        'dt': '588712d8952a590049bb0f47',
        'fi': '123',
    }
    obj_binds = BindsPermissions(**binds)
    obj_binds.validate()
    assert obj_binds.serialized_binds == binds


def test_serialized_binds_with_invalid_data():
    with pytest.raises(ValidationError):
        binds = {
            'pr': '22',
        }
        obj_binds = BindsPermissions(**binds)
        obj_binds.validate()