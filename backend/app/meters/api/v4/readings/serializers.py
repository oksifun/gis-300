from rest_framework.serializers import Serializer
from rest_framework.fields import DateTimeField, FloatField, NullBooleanField, \
    ListField, CharField
from rest_framework_mongoengine.fields import ObjectIdField, FileField

from api.v4.serializers import BaseCustomSerializer
from lib.helpfull_tools import DateHelpFulls as dhf


class CabinetMeterListsSerializer(BaseCustomSerializer):
    month_from = DateTimeField(required=False)
    month_till = DateTimeField(required=False)


class CabinetReadingsSerializer(Serializer):
    id = ObjectIdField()
    values = ListField(child=FloatField())  # required=True


class CabinetMetersSerializer(BaseCustomSerializer):
    meters = CabinetReadingsSerializer(many=True)


class MeterReadingsSerializer(Serializer):
    period = DateTimeField(required=True)
    values = ListField(
        child=FloatField(),
        allow_empty=True,
        required=False,
        default=[]
    )
    as_deltas = NullBooleanField(default=False)
    comment = CharField(allow_blank=True, required=False)

    def validate_period(self, value):
        return dhf.begin_of_month(value)


class ImportMeterReadingsSerializer(BaseCustomSerializer):
    house_id = ObjectIdField(required=True)
    period = DateTimeField(required=True)
    meter_file = FileField(required=True)
