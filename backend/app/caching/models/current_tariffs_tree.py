from mongoengine import ReferenceField, DynamicField, ListField, ObjectIdField, \
    EmbeddedDocumentListField, EmbeddedDocument, StringField, IntField, \
    DateTimeField, BooleanField
from mongoengine.document import Document


class CurrentTariffsTree(Document):
    """
    Текущее дерево тарифов

    Схема дерева:
    список объектов типа:

    -тарифный план:
    --ид
    --наименование
    --дата
    --список тарифов:
    ---ид
    ---наименование
    ---ид услуги
    ---тариф
    ---описание

    -папка:
    --ид папки
    --наименование
    --вложенный список объектов

    """

    meta = {
        'db_alias': 'cache-db',
        'collection': 'current_tariffs_tree',
    }

    provider = ReferenceField('processing.models.billing.provider.Provider')
    tree = DynamicField()


class TariffShortData(EmbeddedDocument):
    """
    Краткое описание тарифа
    """
    _id = ObjectIdField()
    title = StringField()
    service_type = ObjectIdField()
    value = IntField()
    description = StringField()


class TariffsGroupShortData(EmbeddedDocument):
    """
    Краткое описание группы тарифов
    """
    group = IntField()
    tariffs = EmbeddedDocumentListField(TariffShortData)


class TariffPlanShortData(EmbeddedDocument):
    """
    Краткое описание тарифного плана
    """
    id = ObjectIdField(db_field='_id')
    title = StringField()
    date_from = DateTimeField()
    created = DateTimeField()
    tariffs = EmbeddedDocumentListField(TariffsGroupShortData)
    global_values = BooleanField()
    sum_values = BooleanField()

    @classmethod
    def from_tariff_plan(cls, tariff_plan):
        result = {
            'id': tariff_plan.pk,
            'title': tariff_plan.title,
            'date_from': tariff_plan.date_from,
            'created': tariff_plan.created,
            'tariffs': [],
            'global_values': False,
            'sum_values': False,
        }
        if len(tariff_plan.global_values) > 0:
            result['global_values'] = True
        if len(tariff_plan.sum_values):
            result['sum_values'] = True
        groups = {}
        for t in tariff_plan.tariffs:
            g = groups.setdefault(t['group'], [])
            g.append(TariffShortData(
                id=t.id,
                title=t.title,
                service_type=t.service_type,
                value=t.value,
                description=t.description,
            ))
        result['tariffs'] = sorted(
            [
                TariffsGroupShortData(group=k, tariffs=v)
                for k, v in groups.items()
            ],
            key=lambda i: i['group']
        )
        return cls(**result)


class TariffsFolder(Document):
    """
    Объект папки с тарифными планами
    """

    meta = {
        'db_alias': 'cache-db',
        'collection': 'tariffs_folder',
    }

    provider = ReferenceField('processing.models.billing.provider.Provider')
    folder_id = ObjectIdField()
    title = StringField()
    sub_folders = ListField(ObjectIdField())
    tariff_plans = EmbeddedDocumentListField(TariffPlanShortData)
    updated = DateTimeField()

