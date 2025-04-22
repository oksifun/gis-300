from unittest import TestCase

from api.v4.models.tests.base import TestMixin


class TestHouseCrud(TestMixin, TestCase):
    MODEL_URL = "http://localhost:8000/api/v4/models/houses/"

    def test_patch(self):
        self.run_simple_patch_test()
