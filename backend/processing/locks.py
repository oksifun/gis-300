from uuid import uuid4

from mongoengine.errors import NotUniqueError

from .models.lock import AccountTaskLock


class AccountsAreLocked(Exception):
    pass


def acquire_accounts_task_locks(task: str, accounts: list) -> list:
    """ Create database-level locks for every account in accounts list,
    marking them as used by task.
    Locks must be released manually after use with *release()* method.
    :param task: Task instance
    :param accounts: list of Account instances
    :return: list of AccountTaskLock instances if locks acquired, else False
    """

    uuid = uuid4().hex
    new_lock_list = [
        AccountTaskLock(task=task, account=account, uuid=uuid)
        for account in accounts
    ]
    if not new_lock_list:
        return new_lock_list

    try:
        new_lock_list = AccountTaskLock.objects.insert(new_lock_list)
    except NotUniqueError:
        AccountTaskLock.objects(uuid=uuid).delete()
        raise AccountsAreLocked()
    return new_lock_list


def release_accounts_task_locks(locks: list):
    uuid = {lock.uuid for lock in locks}
    uuid = uuid.pop() if len(uuid) == 1 else None
    if uuid:
        AccountTaskLock.objects(uuid=uuid).delete()
    else:
        AccountTaskLock.objects(pk__in=[l.pk for l in locks]).delete()


class AccountLockContext:

    def __init__(self, task, accounts: list):
        self.locks = acquire_accounts_task_locks(task, accounts)

    def __enter__(self):
        return self.locks

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.locks:
            for lock in self.locks:
                lock.release()

