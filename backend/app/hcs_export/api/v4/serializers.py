from rest_framework.fields import CharField
from rest_framework_mongoengine.fields import ObjectIdField
from api.v4.serializers import BaseCustomSerializer


class ExportHcsSerializer(BaseCustomSerializer):
    provider_id = ObjectIdField(required=True)
    email = CharField(required=True)
