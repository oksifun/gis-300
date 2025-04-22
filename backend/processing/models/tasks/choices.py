class TaskStateType(object):
    NEW = 'new'
    FAILED = 'failed'
    FINISHED = 'finished'
    PREPARE = 'prepare'
    WIP = 'wip'
    CANCELED = 'canceled'
    SAVING = 'saving'
    CACHING = 'caching'


TASK_STATE_TYPE_CHOICES = (
    (TaskStateType.NEW, 'Новая'),
    (TaskStateType.FAILED, 'Завершена с ошибкой'),
    (TaskStateType.FINISHED, 'Завершена'),
    (TaskStateType.PREPARE, 'Подготовка'),
    (TaskStateType.WIP, 'В работе'),
    (TaskStateType.CANCELED, 'Отменена'),
    (TaskStateType.SAVING, 'Сохранение изменений'),
    (TaskStateType.CACHING, 'Обновление итогов'),
)
