

class EventType(object):
    INCOMING_CALL = 'incoming_call'
    OUT_COMING_CALL = 'out_coming_call'
    MEETING = 'meeting'
    INFORMATION = 'information'


EVENT_TYPE = (
    (EventType.INCOMING_CALL, 'Входящий звонок'),
    (EventType.OUT_COMING_CALL, 'Исходящий звонок'),
    (EventType.MEETING, 'Встреча'),
    (EventType.INFORMATION, 'Информация'),
)


class EventResult(object):
    GOOD = 'good'
    BAD = 'bad'
    UNKNOWN = 'unknown'


EVENT_RESULT = (
    (EventResult.GOOD, 'хорошо'),
    (EventResult.BAD, 'плохо'),
    (EventResult.UNKNOWN, 'непонятно'),
)


class CRMStatus(object):
    NEW = 'new'
    COLD = 'cold'
    WORK = 'work'
    DENIED = 'denied'
    WRONG = 'wrong'
    ALIEN = 'alien'
    BAN = 'ban'
    CLIENT = 'client'
    PROSPECTIVE_CLIENT = 'prospective_client'
    PARTNER = 'partner'
    DEBTOR = 'debtor'
    ARCHIVE = 'archive'


CRM_STATUS_CHOICE = (
    ('new', 'Новый'),
    ('cold', 'Холодный'),
    ('work', 'В работе'),
    ('denied', 'Отказался'),
    ('wrong', 'Недействующая'),
    ('alien', 'Не наш клиент'),
    ('ban', 'Запрет'),
    ('client', 'Клиент'),
    ('prospective_client', 'Потенциальный'),
    ('partner', 'Партнер'),
    ('departure', 'выезд на адрес'),
    ('aftershock', 'дожимание'),
    ('sent', 'анкета отправлена'),
    ('contract', 'договор/оплата'),
    ('debtor', 'Отключен за долги'),
    ('archive', 'Архивный'),
)

ACTIVE_STATUSES = [CRMStatus.CLIENT, CRMStatus.DEBTOR]
