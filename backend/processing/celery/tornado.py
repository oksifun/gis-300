from functools import partial
import tornado.ioloop


class CeleryResultMixin(object):
    """
    Adds a callback function which could wait for the result asynchronously
    """
    def wait_for_result(self, task, callback):
        if task.ready():
            callback(task.result)
        else:
            tornado.ioloop.IOLoop.instance().add_callback(
                partial(self.wait_for_result, task, callback)
            )
