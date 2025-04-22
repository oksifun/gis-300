from rest_framework import serializers
from rest_framework.fields import CharField

from app.admin.models.choices import LOCAL_BASES_CHOICES, \
    DATA_RESTORE_DATA_TYPES_CHOICES


class RestoreDataSerializer(serializers.Serializer):
    base_name = serializers.ChoiceField(choices=LOCAL_BASES_CHOICES)
    data_type = serializers.ChoiceField(choices=DATA_RESTORE_DATA_TYPES_CHOICES)
    object_id = CharField()
