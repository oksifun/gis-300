import subprocess
import sys

import os

from mongoengine_connections import register_mongoengine_connections

PROCESSING_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(PROCESSING_DIR)
if PROCESSING_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import argparse

from mongoengine import Q
from processing.models.health import Health
import settings
import time


def start_worker(**kwargs):
    python = settings.CHIEF_PYTHON_PATH
    return subprocess.Popen(
        [
            python,
            "{}/worker.py".format(PROCESSING_DIR),
            "--queues", *kwargs["queue_names"],
            "--health", str(kwargs["health"])
        ],
        stdin=None, stdout=None, stderr=None, close_fds=True)


def run(**kwargs):
    # Максимальное количество дочерних процессов, которое контролируется из Chief
    max_processes = kwargs.get('processes', 4)
    processes = []

    while True:
        # ищем все незанятые `health`
        pid = Q(pid__exists=False)
        all_health = Health.objects(pid)

        # на каждый незанятый `health` создаем `worker` и запоминаем его
        for health in all_health:
            if len(processes) < max_processes:
                process_kwargs = dict(kwargs, **dict(health=health.pk))
                p = start_worker(**process_kwargs)
                processes.append(p)

        # проверяем живы ли все созданные этим `chief` дочерные процессы
        old_processes = []
        for process in processes:
            if process.poll() is not None:
                old_processes.append(process)

        for old in old_processes:
            processes.remove(old)

        time.sleep(10)

if __name__ == "__main__":
    register_mongoengine_connections(secondary_prefered=True)

    class Settings(object):
        def __init__(self):
            self.db = "default"
            self.queue_names = []
            self.host = "localhost"
            self.port = 27017
            self.processes = 4
            self.health_id = None

    parser = argparse.ArgumentParser(description='Processing worker daemon')

    parser.add_argument('--db', type=str, help='database instance name')
    parser.add_argument('--queues', dest='queue_names', type=str, nargs='+',
                        help='list of queue names to listen, use space to separate.')
    parser.add_argument('--host', type=str, help='database server host', default='localhost')
    parser.add_argument('--port', type=int, help='database server port', default=27017)
    parser.add_argument('--processes', type=int, help='database server port', default=27017)

    chief_settings = Settings()
    parser.parse_args(namespace=chief_settings)

    run(db=chief_settings.db,
        queue_names=chief_settings.queue_names,
        host=chief_settings.host,
        port=chief_settings.port,
        processes=chief_settings.processes,
        health=chief_settings.health_id)


