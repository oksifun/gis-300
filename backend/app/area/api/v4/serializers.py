from rest_framework.fields import (
    BooleanField, CharField, IntegerField, ListField, DictField
)
from rest_framework.serializers import Serializer
from rest_framework_mongoengine.fields import ObjectIdField
from rest_framework_mongoengine.serializers import (
    DocumentSerializer, EmbeddedDocumentSerializer
)

from app.area.models.area import Area
from processing.models.billing.embeddeds.house import DenormalizedHouseWithFias


class EmbeddedHouseSerializer(EmbeddedDocumentSerializer):

    id = ObjectIdField(read_only=False)

    class Meta:
        model = DenormalizedHouseWithFias
        fields = '__all__'


class AreasSerializer(DocumentSerializer):
    house = EmbeddedHouseSerializer(many=False)
    has_chute = BooleanField(required=False)

    class Meta:
        model = Area
        exclude = (
            '_binds',
            'order',
            'is_deleted',
            'rooms',
            'communications'
        )
        read_only_fields = (
            'str_number',
            'str_number_full',
            'rosreestr',
        )


class MemberPhoneSerializer(Serializer):
    phone_type = CharField(required=False)
    code = CharField(required=False)
    number = CharField(required=True)
    add = CharField(required=False)
    not_actual = BooleanField(required=False)


class OwnershipSerializer(Serializer):
    verified_with_rosreestr = BooleanField(required=False)


class FamilyMemberSerializer(Serializer):
    id = ObjectIdField()
    _type = ListField(child=CharField())
    has_access = BooleanField(required=False)
    str_name = CharField()
    sex = CharField(required=False)
    email = CharField()
    registered = BooleanField()
    living = BooleanField()
    is_owner = BooleanField()
    phones = MemberPhoneSerializer(many=True)
    is_responsible = BooleanField()
    is_renter = BooleanField()
    is_coop_member = BooleanField()
    is_archive = BooleanField()
    property_share = ListField(child=IntegerField(), required=False)
    reverse_role = ObjectIdField(required=False)
    ownership = OwnershipSerializer(required=False)


class FamilySerializer(Serializer):
    id = ObjectIdField()
    name = CharField()
    is_archive = BooleanField()
    members = FamilyMemberSerializer(many=True)
    property_share = ListField(child=IntegerField())
    registered_count = IntegerField()
    living_count = IntegerField()
    rooms = ListField(child=ObjectIdField(), required=False)
    ownership = OwnershipSerializer(required=False)


class RequestSerializer(Serializer):
    account__area__id = ListField(child=ObjectIdField())
    other_tenants_include = BooleanField(required=False, default=False)
