class GisManagerContext:
    """Контекст выполнения (менеджера) операции"""
    INIT = 'init'
    LOAD = 'load'
    PREPARE = 'prepare'
    SPREAD = 'spread'
    REQUEST = 'request'
    ACK = 'ack'
    STATE = 'state'
    PARSE = 'parse'
    STORE = 'store'


GIS_MANAGER_CONTEXTS = {
    GisManagerContext.INIT: 'выполнения инициализации',
    GisManagerContext.LOAD: 'загрузки данных',  # guids?
    GisManagerContext.PREPARE: 'подготовки данных запроса',  # record
    GisManagerContext.SPREAD: 'разбора аргументов',  # record
    GisManagerContext.REQUEST: 'формирования запроса',  # guids
    GisManagerContext.ACK: 'получения квитанции',  # record
    GisManagerContext.STATE: 'получения состояния',  # record
    GisManagerContext.PARSE: 'извлечения результата',  # guids
    GisManagerContext.STORE: 'сохранения результата',  # record, guids
}

NO_RECORD_CONTEXTS: set = {
    GisManagerContext.INIT,
    GisManagerContext.LOAD,
    GisManagerContext.REQUEST,
    GisManagerContext.PARSE,
}  # не сохраняющие запись об операции без ошибки контексты


class GisTaskStateType:
    NEW = 'new'
    WORK = 'work'
    RESTART = 'restart'
    DONE = 'done'


GIS_TASK_STATE_CHOICES = (
    (GisTaskStateType.NEW, "Новая"),
    (GisTaskStateType.WORK, "В работе"),
    (GisTaskStateType.RESTART, "Перезапуск"),
    (GisTaskStateType.DONE, "Решена"),
)

GIS_TASK_STATES = {key: value for (key, value) in GIS_TASK_STATE_CHOICES}


class GisRecordStatusType:
    CREATED = 'new'
    PREPARED = 'pre'
    REQUEST = 'req'
    EXECUTING = 'exec'
    PROCESSING = 'proc'
    DONE = 'done'
    WARNING = 'warn'
    ERROR = 'err'
    PENDING = 'wait'
    CANCELED = 'cxl'


GIS_RECORD_STATUS_CHOICES = (
    (GisRecordStatusType.CREATED, 'Создана'),  # новая
    (GisRecordStatusType.PREPARED, 'Подготовлена'),  # к выполнению
    (GisRecordStatusType.REQUEST, 'Формируется'),  # запрос операции
    (GisRecordStatusType.EXECUTING, 'Выполняется'),  # ГИС ЖКХ
    (GisRecordStatusType.PROCESSING, 'Обработка'),  # результата
    (GisRecordStatusType.DONE, 'Завершена'),  # успешно
    (GisRecordStatusType.WARNING, 'Выполнена'),  # с предупреждениями
    (GisRecordStatusType.ERROR, 'Не выполнена'),  # с ошибкой
    (GisRecordStatusType.PENDING, 'Отложена'),  # ожидает
    (GisRecordStatusType.CANCELED, 'Отменена'),
)

GIS_RECORD_STATUSES = {key: value for (key, value) in GIS_RECORD_STATUS_CHOICES}

SUCCESSFUL_STATUSES = (
    GisRecordStatusType.WARNING,  # Выполнена
    GisRecordStatusType.DONE,  # Завершена
)  # возможные состояния выполненной операции

CANCELABLE_STATUSES = (
    GisRecordStatusType.CREATED,  # Создана
    GisRecordStatusType.REQUEST,  # Формируется
    GisRecordStatusType.PREPARED,  # Подготовлена
    GisRecordStatusType.PENDING,  # Отложена
)  # возможные состояния отменяемой операции

IDLE_RECORD_STATUSES = (
    GisRecordStatusType.CREATED,
    GisRecordStatusType.PREPARED,
    GisRecordStatusType.REQUEST,
    GisRecordStatusType.PENDING,
    GisRecordStatusType.CANCELED,
)  # TODO пополнить список состояний бесперспективных операций

GIS_RECORD_OLD_STATUS_CHOICES = (
    ('created', '-Создана-'),
    ('pending', '-Ожидает-'),
    ('canceled', '-Отменена-'),
    ('request', '-Формируется-'),
    ('process', '-Выполняется-'),
    ('result', '-Обработана-'),
    ('success', '-Завершена-'),
    ('warning', '-Выполнена-'),
    ('error', '-Ошибка-'),
    ('unknown', '-Не определено-'),
    ('wip', '-Выполняется-'),
    ('storing', '-Завершается-'),  # сохранение
    ('finished', '-Успешно завершена-'),
    ('warnings', '-С предупреждениями-'),
)  # TODO удалить после миграции


class GisOperationType:
    GET_STATE = 'getState'  # общий метод получения результата операции

    EXPORT_ORG_REGISTRY = 'exportOrgRegistry'
    EXPORT_NSI_LIST = 'exportNsiList'
    EXPORT_NSI_ITEM = 'exportNsiItem'
    EXPORT_NSI_PAGING_ITEM = 'exportNsiPagingItem'
    EXPORT_DATA_PROVIDER_NSI_ITEM = 'exportDataProviderNsiItem'
    IMPORT_ADDITIONAL_SERVICES = 'importAdditionalServices'
    IMPORT_MUNICIPAL_SERVICES = 'importMunicipalServices'
    IMPORT_GENERAL_NEEDS_MUNICIPAL_RESOURCE = \
        'importGeneralNeedsMunicipalResource'
    EXPORT_CACH_DATA = 'exportCAChData'
    IMPORT_CHARTER_DATA = 'importCharterData'
    EXPORT_BRIEF_HOUSE_DATA = 'exportBriefBasicHouse'
    EXPORT_BRIEF_APARTMENT_HOUSE = 'exportBriefApartmentHouse'
    EXPORT_HOUSE_DATA = 'exportHouseData'
    IMPORT_HOUSE_UO_DATA = 'importHouseUOData'
    EXPORT_ACCOUNT_DATA = 'exportAccountData'
    IMPORT_ACCOUNT_DATA = 'importAccountData'
    EXPORT_METERING_DEVICE_DATA = 'exportMeteringDeviceData'
    IMPORT_METERING_DEVICE_DATA = 'importMeteringDeviceData'
    EXPORT_METERING_DEVICE_HISTORY = 'exportMeteringDeviceHistory'
    IMPORT_METERING_DEVICE_VALUES = 'importMeteringDeviceValues'
    EXPORT_NOTIFICATIONS_ORDER_EXECUTION = 'exportNotificationsOfOrderExecution'
    EXPORT_PAYMENT_DOCUMENT_DATA = 'exportPaymentDocumentData'
    IMPORT_PAYMENT_DOCUMENT_DATA = 'importPaymentDocumentData'
    WITHDRAW_PAYMENT_DOCUMENT_DATA = 'withdrawPaymentDocumentData'
    IMPORT_ACKNOWLEDGMENT = 'importAcknowledgment'


GIS_OPERATION_CHOICES = (
    (GisOperationType.EXPORT_ORG_REGISTRY,
        "Загрузка данных организации"),
    (GisOperationType.EXPORT_NSI_LIST,
        "Загрузка группы общих справочников"),
    (GisOperationType.EXPORT_NSI_ITEM,
        "Загрузка общего справочника"),
    (GisOperationType.EXPORT_NSI_PAGING_ITEM,
        "Постраничная загрузка общего справочника"),
    (GisOperationType.EXPORT_DATA_PROVIDER_NSI_ITEM,
        "Загрузка частного справочника организации"),
    (GisOperationType.IMPORT_ADDITIONAL_SERVICES,
        "Выгрузка справочника дополнительных услуг организации"),
    (GisOperationType.IMPORT_MUNICIPAL_SERVICES,
        "Выгрузка справочника коммунальных услуг организации"),
    (GisOperationType.IMPORT_GENERAL_NEEDS_MUNICIPAL_RESOURCE,
        "Выгрузка справочника коммунальных ресурсов на ОДН в МКД"),
    (GisOperationType.EXPORT_CACH_DATA,
        "Загрузка устава управляющей организации"),
    (GisOperationType.IMPORT_CHARTER_DATA,
        "Выгрузка устава управляющей организации"),
    (GisOperationType.EXPORT_BRIEF_HOUSE_DATA,
        "Экспорт краткой информации о доме"),
    (GisOperationType.EXPORT_BRIEF_APARTMENT_HOUSE,
        "Экспорт краткой информации об МКД"),
    (GisOperationType.EXPORT_HOUSE_DATA,
        "Загрузка данных дома и помещений"),
    (GisOperationType.IMPORT_HOUSE_UO_DATA,
        "Выгрузка данных управляемого УО дома и помещений"),
    (GisOperationType.EXPORT_ACCOUNT_DATA,
        "Загрузка данных лицевых счетов"),
    (GisOperationType.IMPORT_ACCOUNT_DATA,
        "Выгрузка данных лицевых счетов"),
    (GisOperationType.EXPORT_METERING_DEVICE_DATA,
        "Загрузка данных приборов учета"),
    (GisOperationType.IMPORT_METERING_DEVICE_DATA,
        "Выгрузка данных приборов учета"),
    (GisOperationType.EXPORT_METERING_DEVICE_HISTORY,
        "Загрузка показаний приборов учета"),
    (GisOperationType.IMPORT_METERING_DEVICE_VALUES,
        "Выгрузка показаний приборов учета"),
    (GisOperationType.EXPORT_NOTIFICATIONS_ORDER_EXECUTION,
        "Загрузка перечня извещений о принятии к исполнению распоряжений"),
    (GisOperationType.EXPORT_PAYMENT_DOCUMENT_DATA,
        "Загрузка платежных документов"),
    (GisOperationType.IMPORT_PAYMENT_DOCUMENT_DATA,
        "Выгрузка платежных документов"),
    (GisOperationType.WITHDRAW_PAYMENT_DOCUMENT_DATA,
        "Отзыв платежных документов"),
    (GisOperationType.IMPORT_ACKNOWLEDGMENT,
        "Запросы на проведение или отмену квитирования")
)  # export - из ГИС ЖКХ, import - в ГИС ЖКХ


class GisGUIDStatusType:
    SAVED = 'saved'
    NEW = 'new'
    CHANGED = 'changed'
    WIP = 'wip'
    NO_RESULT = 'no_result'
    ERROR = 'error'
    UNKNOWN = 'unknown'


GIS_GUID_STATUS_CHOICES = (
    (GisGUIDStatusType.SAVED, 'Сохранено'),
    (GisGUIDStatusType.NEW, 'Новая'),
    (GisGUIDStatusType.CHANGED, 'Изменена'),
    (GisGUIDStatusType.WIP, 'В обработке'),
    (GisGUIDStatusType.NO_RESULT, 'Нет результата'),
    (GisGUIDStatusType.ERROR, 'Ошибка'),
    (GisGUIDStatusType.UNKNOWN, 'Не определено'),
)


class GisObjectType:
    PROVIDER = 'Provider'
    LEGAL_ENTITY = 'LegalEntity'
    CHARTER = 'Charter'
    CONTRACT = 'Contract'
    HOUSE = 'House'
    PORCH = 'Porch'
    LIFT = 'Lift'
    AREA = 'Area'
    ROOM = 'Room'
    UO_ACCOUNT = 'UOAccount'
    CR_ACCOUNT = 'CRAccount'
    TKO_ACCOUNT = 'TKOAccount'
    RSO_ACCOUNT = 'RSOAccount'
    RC_ACCOUNT = 'RCAccount'
    OGV_OMS_ACCOUNT = 'OGVorOMSAccount'
    AREA_METER = 'AreaMeter'
    HOUSE_METER = 'HouseMeter'
    ACCRUAL = 'Accrual'
    NOTIFICATION = 'NotificationOfExecution'
    CONTRACT_OBJECT = 'ContractObject'  # ~ ServiceBind
    SERVICE_TYPE = 'ServiceTypeGisName'
    ATTACHMENT = 'Attachment'


GIS_OBJECT_CHOICES = (
    (GisObjectType.PROVIDER, "Организация"),
    (GisObjectType.LEGAL_ENTITY, "Юридическое лицо"),
    (GisObjectType.CHARTER, "Устав организации"),
    (GisObjectType.CONTRACT, "Договор управления"),
    (GisObjectType.HOUSE, "Дом (здание)"),
    (GisObjectType.AREA, "Квартира (помещение)"),
    (GisObjectType.PORCH, "Подъезд (парадная)"),
    (GisObjectType.ROOM, "Комната"),
    (GisObjectType.UO_ACCOUNT, "ЛС для оплаты КУ"),
    (GisObjectType.CR_ACCOUNT, "ЛС для оплаты КР"),
    (GisObjectType.TKO_ACCOUNT, "ЛС для оплаты вывоза ТКО"),
    (GisObjectType.RSO_ACCOUNT, "ЛС для оплаты КУ РСО"),
    (GisObjectType.RC_ACCOUNT, "ЛС РКЦ"),
    (GisObjectType.OGV_OMS_ACCOUNT, "ЛС органов ГВ или МС"),
    (GisObjectType.AREA_METER, "Индивидуальный ПУ"),
    (GisObjectType.HOUSE_METER, "Общедомовой ПУ"),
    (GisObjectType.ACCRUAL, "Платежный документ"),
    (GisObjectType.NOTIFICATION, "Уведомление о квитировании"),
    (GisObjectType.CONTRACT_OBJECT, "Объект управления"),
    (GisObjectType.SERVICE_TYPE, "Предоставляемая услуга"),
)

GIS_OLD_OBJECT_CHOICES = (
    ('Tenant', "-Лицевой счет-"),
    ('ServiceBind', '-Объект управления-'),
)  # TODO удалить после миграции
