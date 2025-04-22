from rest_framework.fields import CharField, IntegerField, FloatField, \
    DateTimeField, BooleanField
from rest_framework.serializers import Serializer, ListField
from rest_framework_mongoengine.fields import ObjectIdField

from api.v4.serializers import CustomDocumentSerializer
from app.payment.models.vendor_pay_doc import VendorPaymentDoc
from app.payment.models.vendor_receipt_doc import VendorReceiptDoc


class VendorPaymentSerializer(CustomDocumentSerializer):
    class Meta:
        model = VendorPaymentDoc
        fields = (
            'id',
            'vendor',
            'contract',
            'value',
            'state',
            'code',
            'description',
            'date',
            'source_date',
            'bank_account',
        )
        read_only_fields = (
            'id',
            'vendor',
            'contract',
            'value',
            'source_date',
        )


class VendorReceiptDocSerializer(CustomDocumentSerializer):
    class Meta:
        model = VendorReceiptDoc
        fields = (
            'id',
            'value',
            'count',
            'number',
            'description',
            'date',
            'bank_number',
            'bank',
            'fiscalization_at',
        )


class VendorPaymentReceiptsSerializer(Serializer):
    offset = IntegerField(default=0, min_value=0)
    limit = IntegerField(default=20, max_value=50, min_value=1)


class VendorPaymentReceiptSerializer(Serializer):
    id = ObjectIdField()
    account_name = CharField(required=False)
    account_address = CharField(required=False)
    value = IntegerField()
    penalty_included = IntegerField(required=False)
    sector = CharField(required=False)
    has_receipt = BooleanField(default=False)
    date = DateTimeField(required=False)


class VendorPaymentCreateFeeSerializer(Serializer):
    fee = FloatField(required=True)
    houses = ListField(
        child=ObjectIdField(),
        required=False,
    )


class VendorPaymentCreateServiceSerializer(Serializer):
    id = ObjectIdField(required=True)
    fees = ListField(
        child=VendorPaymentCreateFeeSerializer(),
        required=False,
    )


class VendorPaymentCreateByServicesSerializer(Serializer):
    services = ListField(
        child=VendorPaymentCreateServiceSerializer(),
        required=False,
    )

    contract = ObjectIdField(required=True)
    date = DateTimeField(required=True)
    source_date = DateTimeField(required=True)
    bank_account = CharField(required=True)

    def create(self, validated_data, owner_id):
        doc = self.get_object(validated_data, owner_id)
        doc.save()
        return doc

    def get_object(self, validated_data, owner_id):
        doc = VendorPaymentDoc(
            owner=owner_id,
            contract=validated_data['contract'],
            date=validated_data['date'],
            source_date=validated_data['source_date'],
            bank_account=validated_data['bank_account'],
            value=0,
        )
        return doc


class VendorPaymentCreateSerializer(CustomDocumentSerializer):

    class Meta:
        model = VendorPaymentDoc
        fields = (
            'id',
            'owner',
            'vendor',
            'contract',
            'value',
            'state',
            'code',
            'description',
            'date',
            'source_date',
            'bank_account',
        )
        read_only_fields = (
            'id',
            'vendor',
            'state',
            'code',
        )


class VendorPaymentReportParametersSerializer(Serializer):
    contract = ObjectIdField(required=False)
    date = DateTimeField(required=True)


class VendorPaymentHouseSerializer(Serializer):
    id = ObjectIdField()
    address = CharField()
    balance_in = IntegerField()
    paid = IntegerField()
    transfered = IntegerField()
    for_transfer = IntegerField()


class VendorPaymentFeeSerializer(Serializer):
    fee = FloatField()
    name = CharField()
    houses = ListField(child=VendorPaymentHouseSerializer())
    balance_in = IntegerField()
    paid = IntegerField()
    transfered = IntegerField()
    for_transfer = IntegerField()


class VendorPaymentServiceSerializer(Serializer):
    id = ObjectIdField()
    name = CharField()
    fees = ListField(child=VendorPaymentFeeSerializer())
    balance_in = IntegerField()
    paid = IntegerField()
    transfered = IntegerField()
    for_transfer = IntegerField()


class VendorPaymentBankAccountSerializer(Serializer):
    number = CharField()
    services = ListField(child=VendorPaymentServiceSerializer())
    balance_in = IntegerField()
    paid = IntegerField()
    transfered = IntegerField()
    for_transfer = IntegerField()


class VendorPaymentAgreementSerializer(Serializer):
    id = ObjectIdField()
    name = CharField()
    number = CharField()
    bank_accounts = ListField(child=VendorPaymentBankAccountSerializer())
    balance_in = IntegerField()
    paid = IntegerField()
    transfered = IntegerField()
    for_transfer = IntegerField()


class VendorPaymentReportDataSerializer(Serializer):
    id = ObjectIdField()
    name = CharField()
    inn = CharField()
    agreements = ListField(child=VendorPaymentAgreementSerializer())
    balance_in = IntegerField()
    paid = IntegerField()
    transfered = IntegerField()
    for_transfer = IntegerField()
