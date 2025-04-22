from mongoengine import Document, EmbeddedDocument, StringField, ListField, \
    FloatField, EmbeddedDocumentField, EmbeddedDocumentListField, DateTimeField, \
    ObjectIdField


class BoilerGraphColumn(EmbeddedDocument):
    header = StringField()
    values = ListField(FloatField())


class BoilerGraph(EmbeddedDocument):
    """
    График работы котельной
    """
    name = StringField()
    t0 = EmbeddedDocumentField(
        BoilerGraphColumn,
        verbose_name='Температура наружнего воздуха',
    )
    tv1 = EmbeddedDocumentListField(
        BoilerGraphColumn,
        verbose_name='Температура на входе',
    )
    tv2 = EmbeddedDocumentListField(
        BoilerGraphColumn,
        verbose_name='Температура на выходе',
    )
    period = ListField(
        DateTimeField(),
        max_length=2,
        min_length=2,
        verbose_name='Период действия графика',
    )


class BoilerDefaultCorrection(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    date = DateTimeField()
    value = FloatField()
    comment = StringField()


class BoilerProviderCorrection(EmbeddedDocument):
    """
    Список корректировок температуры холодной воды для организации
    """
    id = ObjectIdField(db_field='_id')
    provider = ObjectIdField(verbose_name='Организация-владелец корректировки')
    values = EmbeddedDocumentListField(
        BoilerDefaultCorrection,
        verbose_name='Значения корректировок на указанные даты',
    )


class Boiler(Document):
    """
    Котельная
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Boiler',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'houses',
            'region_code',
        ],
    }

    name = StringField(verbose_name='название котельной')
    graphs = EmbeddedDocumentListField(BoilerGraph, verbose_name='график')
    houses = ListField(
        ObjectIdField(),
        verbose_name='дома, прикрепленные к котельной',
    )
    provider = ObjectIdField()
    region_code = StringField()
    default_corrections = EmbeddedDocumentListField(
        BoilerDefaultCorrection,
        verbose_name='корректировки по-умолчанию',
    )
    provider_corrections = EmbeddedDocumentListField(
        BoilerProviderCorrection,
        verbose_name='корректировки организаций',
    )
