from processing.models.tasks.choices import (
    TaskStateType,
    TASK_STATE_TYPE_CHOICES
)


class TaskType:
    CIPCA_TASKS = 'cipca_tasks'
    RECEIPT_TASKS = 'receipt_tasks'


TASK_TYPE_CHOICES = (
    (TaskType.CIPCA_TASKS, 'Задачи на расчет'),
    (TaskType.RECEIPT_TASKS, 'Задачи на печать'),
)


class CipcaTaskType:
    MASS_CREATE_ACCRUAL_DOC = 'mass_create_accrual_doc'
    MASS_CALCULATE_SERVICE_GROUP = 'mass_calculate_service_group'
    MASS_CALCULATE_PENALTIES = 'mass_calculate_penalties'


CIPCA_TASK_TYPE_CHOICES = (
    (CipcaTaskType.MASS_CREATE_ACCRUAL_DOC, 'Формирование документов '
                                             'начислений'),
    (CipcaTaskType.MASS_CALCULATE_SERVICE_GROUP, 'Пересчёт услуг'),
    (CipcaTaskType.MASS_CALCULATE_PENALTIES, 'Пересчёт пеней'),
)


class ReceiptTaskType:
    RUN_CREATING_ALL_RECEIPTS = 'run_creating_all_receipts'


RECEIPT_TASK_TYPE_CHOICES = (
    (ReceiptTaskType.RUN_CREATING_ALL_RECEIPTS, 'Формирование квитанций'),
)


