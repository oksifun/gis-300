from unittest import TestCase

from mongoengine import register_connection

from processing.models.tasks.base import Task


class TestTask(TestCase):
    def setUp(self):
        register_connection('queue-db', name='db_for_testing', host='localhost')
        register_connection('legacy-db', name='db_for_testing', host='localhost')
        self.task = Task()

    def test_process(self):
        self.assertRaises(NotImplementedError, self.task.process)

    def test_meta_has_default_alias(self):
        self.assertEqual(self.task._meta['db_alias'], 'queue-db')
