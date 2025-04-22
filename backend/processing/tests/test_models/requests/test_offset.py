import unittest
from datetime import datetime

from bson import ObjectId
from mongoengine.connection import register_connection

from processing.models.tasks.base import TaskStatus
from app.offsets.models.tasks import OffsetRequestTask
from processing.models.billing.bic import Bic
from processing.models.billing.provider.main import Provider
from processing.models.billing.account import Account, Settings
from processing.models.lock import AccountTaskLock


class OffsetRequestTaskTestCase(unittest.TestCase):

    def setUp(self):
        register_connection('queue-db', name='db_for_testing', host='localhost')
        register_connection('legacy-db', name='db_for_testing', host='localhost')

        self.assertEqual(Account._get_db().name, 'db_for_testing')
        self.assertEqual(OffsetRequestTask._get_db().name, 'db_for_testing')
        self.assertEqual(AccountTaskLock._get_db().name, 'db_for_testing')
        self.assertEqual(Provider._get_db().name, 'db_for_testing')
        self.assertEqual(Bic._get_db().name, 'db_for_testing')
        Account.drop_collection()
        OffsetRequestTask.drop_collection()
        AccountTaskLock.drop_collection()
        Provider.drop_collection()
        Bic.drop_collection()

        self.accounts = [Account(
            number=str(i + 100),
            settings=Settings(),
            has_access=True,
            news_count=0,
            delivery_disabled=True,
            _type='Tenant',
            is_privileged=True,
            is_priviledged=True,
            is_super=True,
            legal_form=""
        ).save() for i in range(5)]

        self.provider = Provider(
            legal_form="ООО",
            bic=[Bic().save()],
            is_agent=False,
        ).save()

        self.tenants = [
            account.id for account in self.accounts
        ]

    def tearDown(self):
        self.assertEqual(Account._get_db().name, 'db_for_testing')
        self.assertEqual(OffsetRequestTask._get_db().name, 'db_for_testing')
        self.assertEqual(AccountTaskLock._get_db().name, 'db_for_testing')
        self.assertEqual(Provider._get_db().name, 'db_for_testing')
        self.assertEqual(Bic._get_db().name, 'db_for_testing')
        Account.drop_collection()
        OffsetRequestTask.drop_collection()
        AccountTaskLock.drop_collection()
        Provider.drop_collection()
        Bic.drop_collection()

    def test_create_offset_tasks(self):
        self.assertEqual(OffsetRequestTask._get_db().name, 'db_for_testing')
        OffsetRequestTask.drop_collection()

        offset_request_task = OffsetRequestTask(
            tenants=self.tenants,
            created=datetime.now(),
            status=TaskStatus.CREATED,
            delayed=None,
            provider=self.provider
        ).save()

        offset_request_task.process()

        tasks_expected = sum([len(task['sectors']) for task in self.tasks])

    def test_done__status_updated(self):
        self.assertEqual(OffsetRequestTask._get_db().name, 'db_for_testing')
        OffsetRequestTask.drop_collection()

        offset_request_task = OffsetRequestTask(
            tenants=self.tenants,
            created=datetime.now(),
            status=TaskStatus.CREATED,
            delayed=None,
            provider=ObjectId("526234b0e0e34c4743821ab6")
        ).save()

        offset_request_task.process()

        self.assertEqual(offset_request_task.status, TaskStatus.DONE)

    def test_done__ended_updated(self):
        self.assertEqual(OffsetRequestTask._get_db().name, 'db_for_testing')
        OffsetRequestTask.drop_collection()

        time = datetime.now()

        offset_request_task = OffsetRequestTask(
            tenants=self.tenants,
            created=datetime.now(),
            status=TaskStatus.CREATED,
            delayed=None,
            ended=time,
            provider=ObjectId("526234b0e0e34c4743821ab6")
        ).save()

        offset_request_task.process()

        self.assertNotEqual(offset_request_task.ended, time)

    def test_process__done(self):
        self.assertEqual(OffsetRequestTask._get_db().name, 'db_for_testing')
        self.assertEqual(AccountTaskLock._get_db().name, 'db_for_testing')
        OffsetRequestTask.drop_collection()
        AccountTaskLock.drop_collection()

        ort = OffsetRequestTask(
            tenants=self.tenants,
            created=datetime.now(),
            status=TaskStatus.CREATED,
            delayed=None,
            provider=ObjectId("526234b0e0e34c4743821ab6")
        ).save()

        ort.process()



