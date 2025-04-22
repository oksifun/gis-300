from app.c300.models.choices import BaseTaskState


class LocalBaseName:
    LOCAL_DEV = 'local_dev'
    LOCAL_ACTUAL = 'local_actual'
    DATA_CENTER_DEV = 'data_center_dev'
    DATA_CENTER_ACTUAL_224 = 'data_center_actual_224'
    DATA_CENTER_ACTUAL_221 = 'data_center_actual_221'


LOCAL_BASES_CHOICES = (
    (LocalBaseName.DATA_CENTER_ACTUAL_224, 'Дата-центр актуальная 224'),
    (LocalBaseName.DATA_CENTER_ACTUAL_221, 'Дата-центр актуальная 221'),
    (LocalBaseName.DATA_CENTER_DEV, 'Дата-центр dev 220'),
    (LocalBaseName.LOCAL_ACTUAL, 'Локальная актуальная'),
    (LocalBaseName.LOCAL_DEV, 'Локальная dev'),
)
LOCAL_BASES_IPS = {
    LocalBaseName.DATA_CENTER_ACTUAL_224: '10.1.1.224',
    LocalBaseName.DATA_CENTER_ACTUAL_221: '10.1.1.221',
    LocalBaseName.DATA_CENTER_DEV: '10.1.1.220',
    LocalBaseName.LOCAL_ACTUAL: '10.100.0.60',
    LocalBaseName.LOCAL_DEV: '10.100.0.19',
}


class DataRestoreDataType:
    HOUSE = 'house'
    PROVIDER_HOUSES = 'house_group'
    AREA = 'area'
    PROVIDER = 'provider_personnel'
    OFFSETS_PROVIDER = 'provider_fin'
    OFFSETS_ACCOUNT = 'account_fin'
    TARIFF_PLAN = 'tariff_plan'
    REGIONAL_SETTINGS = 'regional_settings'
    TELEPHONY = 'telephony'


DATA_RESTORE_DATA_TYPES_CHOICES = (
    (
        DataRestoreDataType.HOUSE,
        'Данные дома (не финансовые)',
    ),
    (
        DataRestoreDataType.PROVIDER_HOUSES,
        'Данные домов организации (не финансовые)',
    ),
    (
        DataRestoreDataType.AREA,
        'Данные помещения (не финансовые)',
    ),
    (
        DataRestoreDataType.PROVIDER,
        'Данные об организации (не финансовые)',
    ),
    (
        DataRestoreDataType.OFFSETS_PROVIDER,
        'Финансовые данные организации',
    ),
    (
        DataRestoreDataType.OFFSETS_ACCOUNT,
        'Финансовые данные ЛС',
    ),
    (
        DataRestoreDataType.TARIFF_PLAN,
        'Тарифный план',
    ),
    (
        DataRestoreDataType.REGIONAL_SETTINGS,
        'Региональные настройки',
    ),
    (
        DataRestoreDataType.TELEPHONY,
        'Телефония',
    ),
)


class DataRestoreTaskState(BaseTaskState):
    pass


DATA_RESTORE_TASK_STATES_CHOICES = (
    (DataRestoreTaskState.NEW, 'создано'),
    (DataRestoreTaskState.WIP, 'в работе'),
    (DataRestoreTaskState.SUCCESS, 'успешно'),
    (DataRestoreTaskState.ERROR, 'ошибка'),
)
