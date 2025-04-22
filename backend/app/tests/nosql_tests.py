from django.test.runner import DiscoverRunner

from rest_framework.test import APITestCase


class NoSQLTestRunner(DiscoverRunner):
    """
    Используется для запуска тестов в Django, предназначен
    для использования с NoSQL базами данных.
    """
    def setup_databases(self, **kwargs):
        pass

    def teardown_databases(self, old_config, **kwargs):
        pass


class NoSQLTestCase(APITestCase):
    """Предназначен для тестирования запросов к NoSQL базам данных."""
    def _fixture_setup(self):
        pass

    def _fixture_teardown(self):
        pass
