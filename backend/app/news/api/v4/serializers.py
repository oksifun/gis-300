from rest_framework_mongoengine.serializers import drf_fields, drfm_fields, \
    DocumentSerializer
from mongoengine import StringField, ListField, ObjectIdField

from api.v4.serializers import CustomEmbeddedDocumentSerializer, \
    CustomDocumentSerializer, BaseCustomSerializer
from app.news.models.news import News
from processing.models.billing.base import ProviderPositionBinds
from rest_framework import serializers

from processing.models.billing.provider.main import Provider

FIELDS = ('created_at', 'subject', 'body', 'author', 'category', 'files',
          'head_img', 'for_providers', 'for_tenants', 'houses', 'fiases',
          'is_published', 'statistics', '_binds', 'id', 'delivery_keys')


class NewsBindsSerializer(CustomEmbeddedDocumentSerializer):
    pr = ListField(ObjectIdField())
    po = ListField(StringField())

    class Meta:
        model = ProviderPositionBinds
        fields = ('pr', 'po')


class NewsCreateSerializer(CustomDocumentSerializer):
    _binds = NewsBindsSerializer(required=True)

    class Meta:
        model = News
        fields = FIELDS


class NewsSerializer(CustomDocumentSerializer):
    class Meta:
        model = News
        fields = FIELDS


class NewsUnreadSerializer(DocumentSerializer):
    provider_str_name = serializers.SerializerMethodField()

    class Meta:
        model = News
        fields = FIELDS + ('provider_str_name',)

    @staticmethod
    def get_provider_str_name(obj):
        provider = Provider.objects(
            id=obj.author.provider
        ).only('str_name').get()
        return provider.str_name


class NewsMarkReadSerializer(BaseCustomSerializer):

    class Meta:
        model = News
        fields = ('id',)


class NewsDailyReportSerializer(BaseCustomSerializer):
    news_id = drfm_fields.ObjectIdField()
    date_from = drf_fields.DateTimeField(required=False)
    date_till = drf_fields.DateTimeField(required=False)
