import unittest
from mongoengine.connection import register_connection
from datetime import datetime, timedelta

from processing.worker import Worker

from processing.models.tasks.base import Task, TaskStatus


class WorkerTestTask(Task):
    _done = False

    def process(self):
        self._done = True


class WorkerTestCase(unittest.TestCase):
    def _reset_worker(self):
        self.worker = Worker('test_db', ['TEST_QUEUE'], pid='worker_pid_1')

    def setUp(self):
        register_connection('queue-db', name='db_for_testing', host='localhost')
        register_connection('legacy-db', name='db_for_testing', host='localhost')

        self._reset_worker()

    def tearDown(self):
        self.assertEqual(Task._get_db().name, 'db_for_testing')
        Task.drop_collection()

    def test_worker_init_bad_queue_type_list(self):
        self.assertRaises(ValueError, Worker, 'test_db', [])
        self.assertRaises(ValueError, Worker, 'test_db', [1, str])
        self.assertRaises(ValueError, Worker, 'test_db', 'task_type')
        self.assertRaises(ValueError, Worker, 'test_db', None)

    def test_worker_init(self):
        # ничего не тестирует
        worker = Worker('test_db', ['TEST_QUEUE'])

        self.assertTrue(hasattr(worker, 'id'))
        self.assertTrue(hasattr(worker, 'host'))
        self.assertTrue(hasattr(worker, 'port'))
        self.assertTrue(hasattr(worker, 'db'))
        self.assertTrue(hasattr(worker, 'queue_names'))
        self.assertTrue(hasattr(worker, 'task'))

    def test_acquire_from_right_queue(self):
        self.assertEqual(Task._get_db().name, 'db_for_testing')
        Task.drop_collection()

        WorkerTestTask(queue='TEST_QUEUE_WRONG', created=datetime.now(), status=TaskStatus.CREATED).save()
        self.worker.acquire_task()

        self.assertIsNone(self.worker.task)

    def test_acquire_task_priority_order(self):
        self.assertEqual(Task._get_db().name, 'db_for_testing')
        Task.drop_collection()

        WorkerTestTask(queue='TEST_QUEUE', created=datetime.now(), status=TaskStatus.CREATED, priority=10).save()
        WorkerTestTask(queue='TEST_QUEUE', created=datetime.now(), status=TaskStatus.CREATED, priority=20).save()

        self.worker.acquire_task()
        self.assertEqual(self.worker.task.priority, 20)

    def test_acquire_task_created_order(self):
        self.assertEqual(Task._get_db().name, 'db_for_testing')
        Task.drop_collection()

        created_second = datetime.now()
        created_first = created_second - timedelta(hours=1)

        WorkerTestTask(queue='TEST_QUEUE', created=created_first, status=TaskStatus.CREATED).save()
        WorkerTestTask(queue='TEST_QUEUE', created=created_second, status=TaskStatus.CREATED).save()

        self.worker.acquire_task()
        self.assertAlmostEqual(self.worker.task.created.timestamp(), created_first.timestamp(), places=1)

    def test_acquire_task_in_progress_not_own(self):
        self.assertEqual(Task._get_db().name, 'db_for_testing')
        Task.drop_collection()
        WorkerTestTask(queue='TEST_QUEUE', created=datetime.now(), status=TaskStatus.WORK_IN_PROGRESS).save()

        self.assertIsNone(self.worker.acquire_task())

    def test_acquire_task_delayed_not_expired(self):
        self.assertEqual(Task._get_db().name, 'db_for_testing')
        Task.drop_collection()
        WorkerTestTask(queue='TEST_QUEUE', created=datetime.now(), status=TaskStatus.CREATED,
                       delayed=datetime.now() + timedelta(hours=1)).save()

        self.assertIsNone(self.worker.acquire_task())

    def test_acquire_task_delayed_expired(self):
        self.assertEqual(Task._get_db().name, 'db_for_testing')
        Task.drop_collection()
        WorkerTestTask(queue='TEST_QUEUE', created=datetime.now(), status=TaskStatus.CREATED, delayed=datetime.now()).save()

        self.worker.acquire_task()
        self.assertIsNotNone(self.worker.task)

    def test_acquire_task_worker_id_update(self):
        self.assertEqual(Task._get_db().name, 'db_for_testing')
        Task.drop_collection()
        WorkerTestTask(queue='TEST_QUEUE', created=datetime.now(), status=TaskStatus.CREATED).save()

        self.worker.acquire_task()
        self.assertEqual(self.worker.task.worker_pid, self.worker.id)

    def test_acquire_task_only_one_taken(self):
        self.assertEqual(Task._get_db().name, 'db_for_testing')
        Task.drop_collection()
        for i in range(5):
            WorkerTestTask(queue='TEST_QUEUE', created=datetime.now(), status=TaskStatus.CREATED).save()

        self.worker.acquire_task()

        self.assertEqual(WorkerTestTask.objects(worker_pid__exists=True).count(), 1)

    def test_loop_task_drop(self):
        self.assertEqual(Task._get_db().name, 'db_for_testing')
        Task.drop_collection()

        WorkerTestTask(queue='TEST_QUEUE', created=datetime.now(), status=TaskStatus.CREATED).save()
        self.worker.loop()
        self.assertIsNone(self.worker.task)

    def test_from_cmd_arguments_parsing(self):
        worker = Worker.from_cmd([
            '--db', 'db-test-string',
            '--queues', 'queue-test-string-1', 'queue-test-string-2', 'queue-test-string-3',
            '--host', 'host-test-string',
            '--port', '12345',
            '--pid', 'pid-test-string',
        ])

        self.assertEqual(worker.db, 'db-test-string')
        self.assertEqual(set(worker.queue_names), {'queue-test-string-1', 'queue-test-string-2', 'queue-test-string-3'})
        self.assertEqual(worker.host, 'host-test-string')
        self.assertEqual(worker.port, 12345)
        self.assertEqual(worker.id, 'pid-test-string')
