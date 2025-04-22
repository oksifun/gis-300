from rest_framework import serializers


class CloseMeterSerializer(serializers.Serializer):
    values = serializers.ListField(
        child=serializers.FloatField(),
        allow_empty=True,
        required=False,
        default=[]
    )
    date = serializers.DateTimeField(required=True)
