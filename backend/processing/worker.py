import locale
import logging
import logging.config as logging_config
import sys

import os

from loggingconfig import DICT_CONFIG
from mongoengine_connections import register_mongoengine_connections

PROCESSING_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(PROCESSING_DIR)
if PROCESSING_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import argparse
import socket
import sys
import time
import traceback
from datetime import datetime, timedelta

from mongoengine import Q

import settings
from processing.models.choices import WorkerStatus, WorkerQueue
from processing.models.health import Health

from processing.models.tasks.base import (
    Task,
    RequestTask,
    TaskStatus,
    ZipSiblingsFilesTask,
)
from processing.models.tasks.gis.accounts import (
    AccountsExportRequest,
    AccountsExportTask,
    AccountsImportRequest,
    AccountsImportTask,
    AccountsIdsImportRequest,
)
from processing.models.tasks.gis.houses import (
    HousesExportRequest,
    HousesExportTask,
    HousesImportRequest,
    HousesImportTask,
)
from processing.models.tasks.gis.meters import (
    MetersInfoExportRequest,
    MetersInfoExportTask,
    AreaMetersReadingsExportTask,
    AreaMetersReadingsExportRequest,
    HouseMetersReadingsExportRequest,
    HouseMetersReadingsExportTask,
    MetersInfoImportRequest,
    MetersInfoImportTask,
    AreaMetersReadingsImportRequest,
    AreaMetersReadingsImportTask,
    HouseMetersReadingsImportRequest,
    HouseMetersReadingsImportTask,
)
from processing.models.tasks.gis.coop_members import (
    CoopMembersInfoExportTask,
    CoopMembersInfoExportRequest,
    CoopMembersInfoImportRequest,
    CoopMembersInfoImportTask,
)
from processing.models.tasks.gis.capital_repair import (
    CapitalRepairInfoExportTask,
    CapitalRepairInfoExportRequest,
    CapitalRepairInfoImportRequest,
    CapitalRepairInfoImportTask,
)
from processing.models.tasks.gis.payments import (
    PaymentsExportTask,
    PaymentsImportTask,
    PaymentsExportRequest,
    PaymentsImportRequest,
)
from processing.models.tasks.gis.areas import (
    AreasIdsDataImporter,
    AreasIdsImportTask,
    AreasIdsImportRequest,
)


logger = logging.getLogger('c300')


class Worker:
    def __init__(self, db=None, queue_names=None, host='localhost', port=27017,
                 health=None, solo=False, **kwargs):
        logger.info('Starting worker')
        self.pid = os.getpid()
        self.hostname = socket.gethostname()

        self.host = host
        self.port = port
        self.db = db
        self.queue_names = queue_names
        self.solo = solo

        self.task = None
        self.tasks_is_empty = False
        self.last_heartbeat = datetime.now()
        self.status = WorkerStatus.OK

        if not solo:
            # Воркер забирает себе `health` если он не занят другим воркером
            pid = Q(pid__not__exists=True) | Q(pid=None)
            query = Q(pk=health) & pid

            Health.objects(
                query,
            ).modify(
                hostname=self.hostname,
                pid=self.pid,
                heartbeat=self.last_heartbeat,
                queues=self.queue_names,
            )

        if not isinstance(self.queue_names, list) or not self.queue_names:
            raise ValueError('require non-empty list of queue types')

        if not all([isinstance(name, str) for name in queue_names]):
            raise ValueError('strings only permitted in queue list')

    def acquire_task(self):
        """ Воркер ищет задачу """
        status = Q(status=TaskStatus.CREATED)
        delay = Q(delayed__not__exists=True) | Q(delayed__lte=datetime.now())

        if self.status == WorkerStatus.MAINTENANCE:
            # Если воркер остановлен на обслуживание то ищутся только
            # технические таски,
            # вроде `перевести все задачи с ошибками в статус новая` или
            # `освободить все блокировки жителей`
            queue = Q(queue=WorkerQueue.MAINTENANCE)
        else:
            queue = Q(queue__in=self.queue_names)
        identifier = "{hostname}:{pid}".format(
            hostname=self.hostname,
            pid=self.pid,
        )
        pid = (
                Q(worker_pid=identifier)
                | Q(worker_pid__not__exists=True)
                | Q(worker_pid=None)
        )
        query = status & delay & queue & pid

        # атомарно (надеюсь) занимаем задачу
        task = Task.objects(
            query,
        ).order_by(
            '-priority',
            'created',
        ).limit(1).modify(
            worker_pid=identifier,
            new=True,
        )

        if task:
            self.task = task

    def loop(self):
        self.acquire_task()

        if self.task:
            logger.info('Got task %s: %s', self.pid, self.task.id)
            self.task.process()
            logger.info('Finished task %s: %s', self.pid, self.task.id)

            self.task.worker_pid = None
            self.task.save()

            self.task = None
            self.tasks_is_empty = False
        else:
            self.tasks_is_empty = True

    def heartbeat(self, seconds=5):
        heartbeat = datetime.now()
        delta = heartbeat - self.last_heartbeat
        if delta > timedelta(seconds=seconds):
            processing_health = Health.objects(
                pid=self.pid,
                hostname=self.hostname,
            )

            # если воркер нашел свой `health`, то обновляем статус
            if len(processing_health):
                health = processing_health[0]
                health.heartbeat = heartbeat
                health.save()

                self.last_heartbeat = heartbeat
                self.status = health.status
            else:
                # воркер не видит смысла жить
                sys.exit(0)

    def start(self):
        logger.info('Started %s', self.pid)
        while True:
            try:
                if not self.solo:
                    self.heartbeat(seconds=5)
                if self.tasks_is_empty:
                    time.sleep(5)
                self.loop()

            # попытка удалить мусор при неожиданном завершении
            except KeyboardInterrupt:
                print('Worker stops: KeyboardInterrupt')
                if not self.solo:
                    Health.objects(
                        pid=self.pid,
                        hostname=self.hostname,
                    ).delete()
                sys.exit()

            # попытка залогать ошибку задачи либо в саму задачу, либо в `sentry`
            except Exception as e:
                if self.task:
                    self.task.exception = traceback.format_exc()

                if not settings.DEVELOPMENT:
                    logger.error('Error %s: %s', self.pid, str(e))
                else:
                    raise e
            finally:
                # попытка удалить мусор при неожиданном завершении
                if self.task:
                    self.task.status = TaskStatus.ERROR
                    self.task.worker_pid = None
                    self.task.save()

                    self.task = None

    @classmethod
    def from_cmd(cls, args):
        parser = argparse.ArgumentParser(description='Processing worker daemon')

        parser.add_argument(
            '--db',
            type=str,
            help='database instance name',
        )
        parser.add_argument(
            '--queues',
            dest='queue_names',
            type=str,
            nargs='+',
            help='list of queue names to listen, use space to separate.',
        )
        parser.add_argument(
            '--host',
            type=str,
            help='database server host',
            default='localhost',
        )
        parser.add_argument(
            '--port',
            type=int,
            help='database server port',
            default=27017,
        )
        parser.add_argument(
            '--solo',
            help='work without chief',
            action='store_true',
        )
        parser.add_argument(
            '--health',
            type=str,
            help='health id',
        )

        return Worker(**vars(parser.parse_args(args)))


if __name__ == '__main__':  # pragma: no cover
    register_mongoengine_connections(secondary_prefered=True)
    logging_config.dictConfig(DICT_CONFIG)
    locale.setlocale(locale.LC_ALL, settings.DEFAULT_LOCALE)
    os.environ['TZ'] = 'Europe/Moscow'
    Worker.from_cmd(sys.argv[1:]).start()
