from mongoengine.base.fields import ObjectIdField
from mongoengine.document import Document, EmbeddedDocument
from mongoengine.fields import StringField, ListField, EmbeddedDocumentField


class EmbeddedSystemPosition(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")

    ChiefPosition = (
        ('ch1', 'Председатель правления'),
        ('ch2', 'Генеральный директор'),
        ('ch3', 'Директор')
    )

    AccountantPosition = (
        ('acc1', 'Главный бухгалтер'),
    )

    code = StringField(
        choices=tuple(ChiefPosition + AccountantPosition)
    )  # Any(ChiefPosition, AccountantPosition),

    title = StringField(min_length=1)  # Required(NonEmptyString),

    @classmethod
    def get_chef_position_codes(cls):
        return [choice[0] for choice in cls.ChiefPosition + cls.AccountantPosition]


class SystemDepartment(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'SystemDepartment',
    }

    id = ObjectIdField(db_field="_id", primary_key=True)

    DepartmentCode = (
        ('support', 'Техническая поддержка'),
        ('direction', 'Дирекция'),
        ('accounting', 'Бухгалтерия'),
        ('clerks', 'Офисные сотрудники'),
        ('staff', 'Персонал'),
    )

    ELECTIVE_DEPARTMENTS = ['Правление ТСЖ', 'Правление ЖСК']

    code = StringField(choices=DepartmentCode)  # DepartmentCode,
    title = StringField(min_length=1)
    positions = ListField(EmbeddedDocumentField(EmbeddedSystemPosition))

