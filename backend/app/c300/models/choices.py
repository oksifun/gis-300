
class BaseTaskState:
    NEW = 'new'
    WIP = 'wip'
    SUCCESS = 'success'
    ERROR = 'error'


BASE_TASK_STATES_CHOICES = (
    (BaseTaskState.NEW, 'создано'),
    (BaseTaskState.WIP, 'в работе'),
    (BaseTaskState.SUCCESS, 'успешно'),
    (BaseTaskState.ERROR, 'ошибка'),
)
