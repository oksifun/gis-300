from rest_framework import serializers
from rest_framework_mongoengine.fields import ObjectIdField
from rest_framework_mongoengine.serializers import (DocumentSerializer,
                                                    EmbeddedDocumentSerializer)

from api.v4.serializers import CustomDocumentSerializer
from app.legal_entity.models.legal_entity_contract import (EntityAgreement,
                                                           LegalEntityContract)
from app.legal_entity.models.legal_entity_provider_bind import (
    LegalEntityProviderBind)
from app.legal_entity.models.legal_entity_service import EntityAgreementService

SERVICE_REQUIRED_FIELDS = (
    'agreement', 'contract', 'entity', 'provider',
)


class AgreementSerializer(EmbeddedDocumentSerializer):
    class Meta:
        model = EntityAgreement
        fields = '__all__'


class LegalEntitySerializer(DocumentSerializer):
    class Meta:
        model = LegalEntityProviderBind
        fields = '__all__'


class ContractHousesSerializer(serializers.Serializer):
    vendor = ObjectIdField(required=True)
    contract = ObjectIdField(required=True)


class LegalEntityPhoneSerializer(serializers.Serializer):
    phone_type = serializers.CharField(required=True)
    code = serializers.CharField(required=False, allow_blank=True,
                                 allow_null=True)
    number = serializers.CharField(required=True)
    add = serializers.CharField(required=False, allow_blank=True,
                                allow_null=True)


class BankAccountSerializer(serializers.Serializer):
    bic = serializers.CharField(default="", allow_blank=True)
    corr_number = serializers.CharField(default="", allow_blank=True)
    number = serializers.CharField(default="", allow_blank=True)
    date_from = serializers.DateTimeField(allow_null=True, required=False)
    active_till = serializers.DateTimeField(allow_null=True, required=False)


class CreateNewLegalEntitySerializer(serializers.Serializer):
    legal_inn = serializers.CharField(required=True)
    phones = LegalEntityPhoneSerializer(many=True)
    legal_name = serializers.CharField(required=True)
    legal_form = serializers.CharField(required=True)
    ogrn = serializers.CharField(default="", allow_blank=True)
    bank_accounts = BankAccountSerializer(many=True, required=False)


class EntityDetailsSerializer(serializers.Serializer):
    date_from = serializers.DateTimeField()
    full_name = serializers.CharField()
    short_name = serializers.CharField()
    legal_form = serializers.CharField()
    inn = serializers.CharField()


class UpdateProducerCreateSerializer(serializers.Serializer):
    producer = ObjectIdField()
    entity_details = EntityDetailsSerializer()


class EntityBankAccountsSerializer(serializers.Serializer):
    bank = ObjectIdField(required=False, default='')
    bic = serializers.CharField(required=False, default='')
    number = serializers.CharField(required=True)
    corr_number = serializers.CharField(required=False, default='',
                                        allow_blank=True)
    date_from = serializers.DateTimeField(allow_null=True, required=False)
    active_till = serializers.DateTimeField(allow_null=True, required=False)


class UpdateProducerUpdateSerializer(serializers.Serializer):
    entity_details = EntityDetailsSerializer(required=False)
    entity_bank_accounts = EntityBankAccountsSerializer(
        many=True,
        required=False
    )


class LegalEntityContractSerializer(DocumentSerializer):
    class Meta:
        model = LegalEntityContract
        fields = '__all__'


class LegalEntityContractListSerializer(CustomDocumentSerializer):
    class Meta:
        model = LegalEntityContract
        fields = (
            'id',
            'name',
            'number',
            'created'
        )


class LegalEntityServiceSerializer(DocumentSerializer):
    class Meta:
        model = EntityAgreementService
        fields = '__all__'


class LegalEntityServiceListSerializer(CustomDocumentSerializer):
    contract = ObjectIdField(required=False)
    agreement = ObjectIdField(required=False)
    entity = ObjectIdField(required=False)

    class Meta:
        model = EntityAgreementService
        fields = '__all__'


class LegalEntityServiceUpdateSerializer(DocumentSerializer):
    class Meta:
        model = EntityAgreementService
        read_only_fields = SERVICE_REQUIRED_FIELDS


class EmbeddedServicesProvisionSerializer(serializers.Serializer):
    measurement = serializers.CharField()
    value = serializers.IntegerField()


class LegalEntityServicesCreateSerializer(serializers.Serializer):
    houses = serializers.ListField(child=ObjectIdField(), allow_empty=False)
    service = ObjectIdField(required=False)
    service_select_type = serializers.CharField(required=False)
    contract = ObjectIdField(required=True)
    agreement = ObjectIdField(required=True)
    entity = ObjectIdField(required=True)
    provider = ObjectIdField(required=True)
    sector = serializers.CharField(required=False, allow_null=True)
    date_from = serializers.DateTimeField(required=True)
    date_till = serializers.DateTimeField(required=False, allow_null=True)
    living_areas = serializers.BooleanField(allow_null=True)
    type_provision = EmbeddedServicesProvisionSerializer(required=False)
    not_living_areas = serializers.BooleanField(allow_null=True)
    parking_areas = serializers.BooleanField(allow_null=True)
    consider_developer = serializers.BooleanField(allow_null=True)
