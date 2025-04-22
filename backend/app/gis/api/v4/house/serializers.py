from rest_framework.fields import ListField, CharField
from rest_framework_mongoengine.fields import ObjectIdField

from utils.drf.base_serializers import BaseCustomSerializer


class HousesSerializer(BaseCustomSerializer):

    houses = ListField(child=ObjectIdField(),
        allow_empty=True, required=False, default=[])

    house_groups = ListField(child=ObjectIdField(),
        allow_empty=True, required=False, default=[])

    fias = ListField(child=CharField(),
        allow_empty=True, required=False, default=[])
