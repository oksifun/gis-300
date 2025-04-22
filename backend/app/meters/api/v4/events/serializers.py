from rest_framework import serializers
from rest_framework_mongoengine.serializers import DocumentSerializer

from app.meters.models.meter_event import MeterReadingEvent


class MeterEventsSerializer(DocumentSerializer):
    str_name = serializers.CharField()

    class Meta:
        model = MeterReadingEvent
        fields = '__all__'
