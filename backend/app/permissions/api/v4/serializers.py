from rest_framework.fields import ListField
from rest_framework_mongoengine import serializers
from rest_framework_mongoengine.fields import ObjectIdField

from api.v4.serializers import BaseCustomSerializer


class TabAvailableSerializer(BaseCustomSerializer):
    tabs_list = ListField(child=ObjectIdField(), required=True)
