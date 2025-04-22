from datetime import datetime

from mongoengine import Document, DateTimeField, StringField, ObjectIdField, \
    IntField, EmbeddedDocumentListField, DictField, ListField, FloatField, \
    EmbeddedDocument, BooleanField

from app.meters.models.choices import IMPORT_READINGS_TASK_STATUSES_CHOICES, \
    ImportReadingsTaskStatus


class FailReading(EmbeddedDocument):
    meter = ObjectIdField()
    serial_number = StringField()
    error = StringField()


class FailMeter(EmbeddedDocument):
    serial_number = StringField()
    error = StringField()


class NotFoundMeter(EmbeddedDocument):
    area_number = StringField()
    meter_type = StringField()
    serial_number = StringField()
    values = StringField()
    points = StringField()
    house_consumption = StringField()
    data_type = StringField()


class ImportMeterReadingsTask(Document):
    meta = {
        'db_alias': 'queue-db',
        'collection': 'ImportMetersReadingsTask',
    }
    created = DateTimeField(required=True, default=datetime.now)
    status = StringField(
        required=True,
        choices=IMPORT_READINGS_TASK_STATUSES_CHOICES,
        default=ImportReadingsTaskStatus.NEW,
    )
    description = StringField(default='', required=False)
    error = StringField(default='')
    house_id = ObjectIdField()
    period = DateTimeField(required=True)
    file = ObjectIdField(required=True)
    celery_task = StringField()
    found = IntField()
    not_found = IntField()
    not_found_meters = EmbeddedDocumentListField(NotFoundMeter)
    fail_readings = EmbeddedDocumentListField(FailReading)
    fail_meters = EmbeddedDocumentListField(FailMeter)


class MeterReadingsImportSettings(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'MeterReadingsImportSettings',
    }
    provider_id = ObjectIdField(null=True)
    parser_func = StringField()
    headers_count = IntField()
    headers = DictField()
    primary_build = BooleanField()


class TempMeterDataReadings(Document):
    meta = {
        'db_alias': 'queue-db',
        'collection': 'TempMeterDataReadings',
    }
    task_id = ObjectIdField(required=True)
    area_number = StringField()
    meter_type = StringField()
    serial_number = StringField()
    values = ListField(FloatField())
    points = ListField(IntField())
    house_consumption = FloatField()
    data_type = StringField()
    meter = ObjectIdField(required=True)
