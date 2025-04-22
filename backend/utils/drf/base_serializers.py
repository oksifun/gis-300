import datetime

from bson import ObjectId
from rest_framework import serializers
from rest_framework_mongoengine.fields import ObjectIdField
from rest_framework_mongoengine.serializers import EmbeddedDocumentSerializer, \
    DocumentSerializer

from processing.models.billing.files import Files


def json_serializer(obj):
    if obj is None:
        return None
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if isinstance(obj, ObjectId):
        return str(obj)
    raise TypeError('Type %s not serializable' % type(obj))


class CustomEmbeddedDocumentSerializer(EmbeddedDocumentSerializer):
    def recursive_save(self, validated_data, instance=None):
        if validated_data is None:
            return instance
        return super().recursive_save(validated_data, instance)


class CustomDocumentSerializer(DocumentSerializer):
    serializer_embedded_nested = CustomEmbeddedDocumentSerializer

    def recursive_save(self, validated_data, instance=None):
        if validated_data is None:
            return instance
        return super().recursive_save(validated_data, instance)

    def restore_read_only_embedded_fields(self, value):
        for name, field in self.get_fields().items():
            if isinstance(field, CustomEmbeddedDocumentSerializer):
                if not hasattr(field.Meta, 'read_only_fields'):
                    continue
                for sub_name in field.Meta.read_only_fields:
                    if value.get(name) and value.get(name).get(sub_name):
                        value[name][sub_name] = self.instance[name][sub_name]


class BaseCustomSerializer(serializers.Serializer):
    """Удобен тем, что при инициализации сразу валидирует параметры"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_valid(raise_exception=True)

    def get_param(self, key):
        return self.validated_data[key]


class AbstractKeySerializer(serializers.Serializer):
    pk = None

    @classmethod
    def get_validated_pk(cls, pk):
        serializer = cls(data=dict(pk=pk))
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data['pk']


class PrimaryKeySerializer(AbstractKeySerializer):
    """Готовый сериалайзер для retrieve или patch контроллеров"""
    pk = ObjectIdField()


class FileFieldSerializer(CustomEmbeddedDocumentSerializer):
    class Meta:
        model = Files
        fields = '__all__'
