import datetime

from mongoengine import Document, ListField, StringField, ReferenceField, \
    DateTimeField, ObjectIdField, EmbeddedDocument, FloatField, \
    EmbeddedDocumentField

from processing.models.choices import READINGS_CREATORS_CHOICES


class MeterReadingsChangedData(EmbeddedDocument):
    new = ListField(FloatField(), verbose_name='Новые показания')
    old = ListField(FloatField(), verbose_name='Старые показания')


class MeterReadingEvent(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Event',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'meter',
        ],
    }

    _type = ListField(StringField())
    meter = ReferenceField(
        'processing.models.billing.meter.Meter',
        required=True,
        verbose_name='Ссылка на счётчик',
    )
    created_at = DateTimeField()
    created_by = ObjectIdField(verbose_name='Кем создано')
    source = StringField(
        verbose_name='Тип источника показания',
        choices=READINGS_CREATORS_CHOICES,
    )
    reading_id = ObjectIdField(verbose_name='id показания')
    period = DateTimeField(required=True, verbose_name='Месяц показания')

    values = EmbeddedDocumentField(
        MeterReadingsChangedData,
        verbose_name='Изменение показаний',
    )
    deltas = EmbeddedDocumentField(
        MeterReadingsChangedData,
        verbose_name='Изменение расходов',
    )

    def save(self, *arg, **kwargs):
        if not self.created_at:
            self.created_at = datetime.datetime.now()
        super().save(*arg, **kwargs)

