from rest_framework.fields import ListField, CharField
from rest_framework.serializers import Serializer
from rest_framework_mongoengine.fields import ObjectIdField

from api.v4.serializers import CustomEmbeddedDocumentSerializer, \
    CustomDocumentSerializer
from app.requests.models.request import EmbeddedControlInfo, Request, \
    EmbeddedMonitoring
from processing.models.billing.embeddeds.phone import DenormalizedPhone


class ControlInfoSerializer(CustomEmbeddedDocumentSerializer):
    class Meta:
        model = EmbeddedControlInfo
        fields = ('desc',)


class RequestControlSerializer(CustomDocumentSerializer):
    control_info = ControlInfoSerializer(many=False)

    class Meta:
        model = Request
        fields = ('control_info',)

    def partial_update(self, instance, validated_data):
        instance.control_info = EmbeddedControlInfo(
            desc=validated_data['control_info']['desc'],
            worker=validated_data['worker'],
            worker_short_name=validated_data['worker_short_name'],
            position=validated_data['position'],
            position_name=validated_data['position_name'],
        )
        instance.save()


class MonitoringMessageSerializer(CustomEmbeddedDocumentSerializer):
    message = CharField(required=True)

    class Meta:
        model = EmbeddedMonitoring


class MonitoringPersonSerializer(CustomEmbeddedDocumentSerializer):
    id = ListField(child=ObjectIdField(), required=True)

    class Meta:
        model = EmbeddedMonitoring


class PhoneEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    class Meta:
        model = DenormalizedPhone
        fields = (
            'phone_type',
            'code',
            'number',
            'add',
        )


class TenantRequestPhonesSerializer(Serializer):
    request = ObjectIdField(allow_null=True, required=False)
    phones = ListField(child=PhoneEmbeddedSerializer(many=False))
    email = CharField(max_length=30, required=False, allow_blank=True)
