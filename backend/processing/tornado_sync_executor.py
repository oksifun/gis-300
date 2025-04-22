from concurrent.futures import ThreadPoolExecutor
from tornado.concurrent import run_on_executor


class TornadoSyncExecutor:
    def __init__(self, threads=16):
        self.executor = ThreadPoolExecutor(threads)

    @run_on_executor
    def run(self, func, *args, **kwargs):
        return func(*args, **kwargs)


_executor = TornadoSyncExecutor()


def run_sync_on_executor(func, *args, **kwargs):
    return _executor.run(func, *args, **kwargs)
