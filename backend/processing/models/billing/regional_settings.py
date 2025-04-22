from bson import ObjectId
from mongoengine import Document, IntField, EmbeddedDocumentListField, \
    EmbeddedDocument, FloatField, StringField, BooleanField, DateTimeField, \
    ListField, ReferenceField, ObjectIdField

from app.caching.models.current_tariffs_tree import TariffPlanShortData
from processing.models.choices import PRIVILEGE_SCOPES_CHOICES, \
    PRIVILEGE_CALC_OPTIONS_CHOICES, SYSTEM_PRIVILEGES_CHOICES, \
    PRIVILEGE_TYPES_CHOICES


class PrivilegeBind(EmbeddedDocument):
    """
    Привязка льготы
    """
    rate = FloatField(required=True, verbose_name='Ставка льготы')
    scope = StringField(
        required=True,
        choices=PRIVILEGE_SCOPES_CHOICES,
        verbose_name='Область распространения'
    )
    calc_option = StringField(
        required=True,
        choices=PRIVILEGE_CALC_OPTIONS_CHOICES,
        verbose_name='Настройка расчёта'
    )
    privilege = StringField(
        required=True,
        choices=SYSTEM_PRIVILEGES_CHOICES,
        verbose_name='Системная категория льготы'
    )
    is_info = BooleanField(
        required=True,
        default=False,
        verbose_name='Признак "Справочная", т.е. монетизированная'
    )
    buffer_name = StringField(
        verbose_name='Имя буфера для сохранения результата'
    )
    isolated = BooleanField(
        required=True,
        default=False,
        verbose_name='Изолированный расчёт для каждого льготника'
    )


class PrivilegeTable(EmbeddedDocument):
    id = ObjectIdField(required=True)
    date_from = DateTimeField(verbose_name='Дата начала действия шаблона')
    date_till = DateTimeField(verbose_name='Дата окончания действия шаблона')
    title = StringField(verbose_name='Наименование шаблона')
    scope = StringField(
        required=True,
        choices=PRIVILEGE_SCOPES_CHOICES,
        verbose_name='Область распространения по умолчанию'
    )
    region_code = IntField(verbose_name='Код региона')
    service_types = ListField(
        ReferenceField('processing.models.billing.service_type.ServiceType'),
        verbose_name='Список услуг'
    )
    property_types = ListField(
        StringField(choices=PRIVILEGE_TYPES_CHOICES),
        verbose_name='Список типов собственности'
    )
    privileges_binds = EmbeddedDocumentListField(
        PrivilegeBind,
        verbose_name='Привязки льготных категорий'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.id:
            self.id = ObjectId()


class RegionalSettings(Document):
    """
    Региональные настройки
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'RegionalSettings',
    }
    region_code = IntField()
    tariff_plans = EmbeddedDocumentListField(TariffPlanShortData)
    privilege_plans = EmbeddedDocumentListField(PrivilegeTable)

    @classmethod
    def get_or_create_by_region_code(cls, region_code):
        result = cls.objects(region_code=region_code).as_pymongo().first()
        if not result:
            result = cls(
                region_code=region_code,
                tariff_plans=[],
                privilege_plans=[],
            )
            result.save()
            return result.to_mongo()
        return result

