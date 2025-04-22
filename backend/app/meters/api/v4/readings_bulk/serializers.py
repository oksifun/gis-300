from rest_framework import serializers
from rest_framework_mongoengine.fields import ObjectIdField

from lib.helpfull_tools import DateHelpFulls as dhf


class MeterReadingsSerializer(serializers.Serializer):
    house = ObjectIdField(required=True)
    period = serializers.DateTimeField(required=True)

    def validate_period(self, value):
        return dhf.start_of_day(value)


class MeterReadingsPeriodSerializer(serializers.Serializer):
    house = ObjectIdField(required=True)


class MeterReadingsExcelSerializer(MeterReadingsSerializer):
    meter_types = serializers.ListField(child=serializers.CharField(),
                                        required=False)


class ExportMetersDataToCSVSerializer(serializers.Serializer):
    house = ObjectIdField(required=True)
    period = serializers.DateTimeField(required=True)

