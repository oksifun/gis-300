import unittest
from datetime import datetime
from mongoengine.connection import register_connection

from processing.models.tasks.base import Task, TaskStatus
from processing.models.billing.account import Account, Settings

from processing.models.lock import AccountTaskLock


class AccountLockTestCase(unittest.TestCase):

    def setUp(self):
        register_connection('queue-db', name='db_for_testing', host='localhost')
        register_connection('legacy-db', name='db_for_testing', host='localhost')

        self.assertEqual(Account._get_db().name, 'db_for_testing')
        self.assertEqual(Task._get_db().name, 'db_for_testing')
        self.assertEqual(AccountTaskLock._get_db().name, 'db_for_testing')
        Account.drop_collection()
        Task.drop_collection()
        AccountTaskLock.drop_collection()

        self.account = Account(
            number=str(100),
            settings=Settings(),
            has_access=True,
            news_count=0,
            delivery_disabled=True,
            _type='Tenant',
            is_privileged=True,
            is_priviledged=True,
            is_super=True,
            legal_form="",
        ).save()

        self.task = Task(queue='TEST_QUEUE', created=datetime.now(), status=TaskStatus.CREATED).save()

    def tearDown(self):
        self.assertEqual(Account._get_db().name, 'db_for_testing')
        self.assertEqual(Task._get_db().name, 'db_for_testing')
        self.assertEqual(AccountTaskLock._get_db().name, 'db_for_testing')
        Account.drop_collection()
        Task.drop_collection()
        AccountTaskLock.drop_collection()

    def test_acquire_accounts_task_locks__locks_released(self):
        AccountTaskLock.drop_collection()

        lock = AccountTaskLock(task=self.task, account=self.account).save()
        lock.release()

        self.assertEqual(AccountTaskLock.objects.count(), 0)

