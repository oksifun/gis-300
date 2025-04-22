from app.celery_admin.workers.config import celery_app
from app.personnel.models.personnel import Worker
from processing.models.billing.account import Account
from processing.models.billing.house_group import HouseGroup
from app.messages.models.messenger import UserTasks
from processing.models.permissions import Permissions, ClientTab


@celery_app.task(
    bind=True,
    max_retries=3,
    soft_time_limit=360,
    default_retry_delay=30
)
def update_users_journals(self, house_id):
    """
    Добавление информации о новой заявке(ах)
    """
    house_group = HouseGroup.objects(houses=house_id).distinct('id')
    accounts = Worker.objects(
        __raw__={
            '_binds_permissions.hg': {'$in': house_group},
            '_type': 'Worker',
        },
    ).distinct(
        'id',
    )
    workers_id = checking_permissions(accounts, 'request_log_list')
    UserTasks.send_notices(workers_id, 'journal', message='update')


@celery_app.task(
    bind=True,
    max_retries=3,
    soft_time_limit=360,
    default_retry_delay=30
)
def update_users_tickets(self, accounts: list):
    """Добавление информации о новом обращении"""
    UserTasks.send_notices(accounts, 'ticket')


@celery_app.task(
    bind=True,
    max_retries=3,
    soft_time_limit=20,
    default_retry_delay=30
)
def import_finished(self, account_id, message, url=None):
    """
    Сообщение о завершении импорта
    """
    UserTasks.send_message(
        account_id,
        message,
        url,
    )
    if url:
        UserTasks.send_notices(
            [account_id],
            'registry',
            message='update',
        )


@celery_app.task(
    bind=True,
    max_retries=3,
    soft_time_limit=360,
    default_retry_delay=30
)
def update_meters_messages(self, house_id, account_id, message):
    """
    Сообщение о завершении этапа импорта показаний счетчиков
    """
    UserTasks.send_notices(
        [account_id],
        'meters',
        message=message,
        obj_id=house_id,
    )


@celery_app.task(
    bind=True,
    max_retries=3,
    soft_time_limit=360,
    default_retry_delay=30
)
def update_users_news(self, query):
    """Добавление информации о новом обращении"""
    accounts = tuple(
        a['_id']
        for a in Account.objects(__raw__={'$or': query}).as_pymongo().only('id')
    )
    UserTasks.send_notices(accounts, 'news')


def checking_permissions(accounts_id, slug):
    """
    Возвращает список id у которых есть права на просмотр указанного разрешения.

    :param accounts_id:[ObjectId(),ObjectId()...]
    :type accounts_id:list

    :param slug:берется из коллекции Tab, чтобы вернуть его id
    :type slug: str

    :return:[ObjectId(),ObjectId()...]
    :rtype: list
    """
    workers_id = []
    tab_id = ClientTab.objects(slug=slug).only('id').first()
    workers_permissions = Permissions.objects(
        actor_id__in=accounts_id
    ).as_pymongo().only('actor_id', f'granular.Tab.{tab_id.id}')
    for permissions in workers_permissions:
        list_of_rights = permissions.get(
            'granular', {}
        ).get('Tab', {}).get(f'{tab_id.id}')
        if list_of_rights:
            if list_of_rights[0].get('permissions', {}).get('r'):
                workers_id.append(permissions['actor_id'])

    return workers_id
