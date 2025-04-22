from celery.app.control import Inspect

from app.celery_admin.workers.config import celery_app as riddler_app


def get_tasks_count():

    inspect: Inspect = riddler_app.control.inspect()

    print('SCHEDULED:', inspect.scheduled())  # в (живой) очереди, без eta
    print('RESERVED:', inspect.reserved())  # взяты в работу исполнителями
    print('ACTIVE:', inspect.active())  # выполняемые исполнителями


if __name__ == '__main__':

    get_tasks_count()
