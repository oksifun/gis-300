from mongoengine import (Document, DateTimeField, EmbeddedDocument,
                         EmbeddedDocumentField, EmbeddedDocumentListField,
                         ObjectIdField, StringField)

from processing.models.billing.files import Files
from processing.models.billing.provider.main import Provider


class NewsEmbedded(EmbeddedDocument):
    _id = ObjectIdField(null=False)
    created_at = DateTimeField()
    head_img = EmbeddedDocumentField(Files)
    subject = StringField()
    body = StringField()
    files = EmbeddedDocumentListField(Files)
    author_provider_name = StringField()


class CachedNews(Document):
    meta = {
        'db_alias': 'cache-db',
        'collection': 'house_news',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'house',
        ],
    }
    house = ObjectIdField()
    news = EmbeddedDocumentListField(NewsEmbedded, default=[])

    @classmethod
    def create_by_news_queryset(cls, house, news_queryset):
        news_list = list(
            news_queryset.only(
                '_id',
                'created_at',
                'head_img',
                'subject',
                'body',
                'files',
                'author.provider',
            ).as_pymongo(),
        )
        allowed_providers = [
            bind.provider
            for bind in house.service_binds
            if bind.provider
        ]
        providers_query = Provider.objects(id__in=allowed_providers)
        provider_names = {
            p['_id']: p['str_name']
            for p in providers_query.only('id', 'str_name').as_pymongo()
        }
        for news in news_list:
            provider_id = news.pop('author')['provider']
            news['author_provider_name'] = provider_names.get(provider_id)
        cls.objects(house=house.id).upsert(news=news_list)
