from rest_framework.serializers import Serializer, CharField
from rest_framework_mongoengine import serializers
from api.v4.serializers import BaseCustomSerializer


class PublicPayCallTaskSerializer(BaseCustomSerializer):
    verification_num = CharField()


class PublicPayCallTaskCreateSerializer(BaseCustomSerializer):
    guest_number = serializers.drf_fields.CharField()


class PublicQrAccountSerializer(BaseCustomSerializer):
    phone = serializers.drf_fields.CharField()
    email = serializers.drf_fields.CharField(required=False)


class PublicQrGetAccountSerializer(BaseCustomSerializer):
    pay_action_id = serializers.drf_fields.CharField()


class PublicQrCreateAccountSerializer(BaseCustomSerializer):
    tenant_addresses = serializers.drf_fields.ListField()
    tenant_id = serializers.drf_fields.CharField()
    sector = serializers.drf_fields.CharField()


class PublicQrUpdateAccountSerializer(BaseCustomSerializer):
    tenant_id = serializers.drf_fields.CharField()
    sector = serializers.drf_fields.CharField()

