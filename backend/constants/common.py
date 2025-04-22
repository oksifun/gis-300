
MONTH_NAMES = [
    'Январь',
    'Февраль',
    'Март',
    'Апрель',
    'Май',
    'Июнь',
    'Июль',
    'Август',
    'Сентябрь',
    'Октябрь',
    'Ноябрь',
    'Декабрь'
]

TASK_STATES = (
    "PENDING",
    "STARTED",
    "RETRY",
    "SUCCESS",
    "FAILURE",
    "PROGRESS",
)

END_TASK_STATES = (
    "SUCCESS",
    "FAILURE",
)

WIP_TASK_STATES = list(set(TASK_STATES) - set(END_TASK_STATES))
