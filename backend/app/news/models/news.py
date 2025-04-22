import datetime

from functools import lru_cache
from itertools import chain

from bson import ObjectId
from dateutil.relativedelta import relativedelta
from django.utils.timezone import now as tznow
from mongoengine import Document, ObjectIdField, StringField, \
    DynamicField, EmbeddedDocumentField, DateTimeField, BooleanField, \
    EmbeddedDocument, IntField, EmbeddedDocumentListField, ListField, Q
from rest_framework.exceptions import ValidationError

from app.caching.tasks.news import recalculate_statistics, update_house_news
from app.house.models.house import House
from app.messages.tasks.users_tasks import update_users_news
from app.news.models.choices import NEWS_CATEGORIES_CHOICES
from app.notifications.tasks.events.news_notify import run_notifications
from processing.data_producers.associated.base import get_binded_houses
from processing.models.billing.base import BindedModelMixin, \
    ProviderPositionBinds, BindsPermissions
from processing.models.billing.files import Files
from processing.models.billing.provider.main import Provider
from utils.crm_utils import get_crm_client_ids

DEFAULT_HOUSE = ObjectId("000000000000000000000000")
DEFAULT_POSITION = 'any'
DEFAULT_FIAS = '00000000-0000-0000-0000-000000000000'
DEFAULT_DELIVERY_KEY = 'ВСЕМ'


class NewsAuthor(EmbeddedDocument):
    id = ObjectIdField()
    provider = ObjectIdField()


class NewsStatistics(EmbeddedDocument):
    providers = IntField()
    workers_access = IntField()
    workers_email = IntField()
    tenants = IntField()
    houses = IntField()


class News(BindedModelMixin, Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'News',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('houses', 'is_published', '-created_at'),
            ('fiases', 'is_published', '-created_at'),
            ('_binds.pr', 'is_published', '-created_at'),
        ],
    }
    body = StringField(required=True)
    author = EmbeddedDocumentField(NewsAuthor)
    subject = StringField(required=True, default='')
    created_at = DateTimeField(required=True, default=tznow)
    updated_at = DateTimeField()
    is_published = BooleanField(required=True, default=False)
    files = EmbeddedDocumentListField(Files)
    head_img = EmbeddedDocumentField(Files, required=False, null=True)
    category = StringField(
        choices=NEWS_CATEGORIES_CHOICES
    )
    for_providers = BooleanField(required=False)
    for_tenants = BooleanField(required=False)
    houses = ListField(ObjectIdField())
    fiases = ListField(StringField())
    statistics = EmbeddedDocumentField(NewsStatistics)
    delivery_keys = ListField(
        StringField(),
        verbose_name='Ключи доступа к новостям',
    )
    _binds = EmbeddedDocumentField(
        ProviderPositionBinds,
    )

    # удалить после миграции
    datetime = DateTimeField()
    is_deleted = BooleanField()
    recipients_filter = DynamicField()

    def save(self, *args, **kwargs):
        created_flag = self._created
        try:
            changed_fields = self._changed_fields
        except AttributeError:
            changed_fields = []
        super().save(*args, **kwargs)
        if created_flag:
            update_house_news.delay(self, method='add')
        if not created_flag:
            from app.setl_home.task.post_data import setl_homes_news
            self.updated_at = tznow()
            if 'is_published' in changed_fields and not self.is_published:
                update_house_news.delay(self, method='delete')
                setl_homes_news.delay(self, deleted=True)
            else:
                update_house_news.delay(self, method='update')
                setl_homes_news.delay(self, deleted=True)
        if self.is_published:
            self.update_users_tasks()
            recalculate_statistics.delay(str(self.id), created_flag)

    @classmethod
    def process_provider_binds(cls, provider_id, **kwargs):
        return 0, 0

    def delete(self, signal_kwargs=None, **write_concern):
        # удалем новость из кэша по дому
        from app.setl_home.task.post_data import setl_homes_news
        update_house_news.delay(self, method='delete')
        setl_homes_news.delay(self, deleted=True)
        super().delete()

    def update_users_tasks(self):
        """Уведомление о новости через мессенджер"""
        query = [self.get_for_supers_data()]
        if self.for_providers:
            query.append(self.get_for_providers_data()[0])
        if self.for_tenants:
            from app.setl_home.task.post_data import setl_homes_news
            for_tenants_query = self.get_for_tenants_data()[0]
            query.append(for_tenants_query)
            run_notifications.delay(
                query=for_tenants_query,
                news_id=self.id,
                provider_id=self.author.provider,
            )
            # Отправка уведомлений в адрес приложения setl home
            setl_homes_news.delay(self)
        update_users_news.delay(query)

    @staticmethod
    def get_for_supers_data():
        """
        Отдает запрос для получения суперюзеров.
        """
        return {'_type': 'Worker', 'has_access': True}

    def get_for_providers_data(self):
        """
        Отдает запрос для получения сотрудников и список организаций. Также
        используется при создании рассылки новостей (аргумент delivery).
        """
        providers_ids = tuple(self._binds['pr']) or ()
        positions = self._binds['po'] or ()
        delivery_keys = tuple(self.delivery_keys)
        query = {'_type': 'Worker', 'has_access': True}
        if positions and DEFAULT_POSITION not in positions:
            query['position.code'] = {'$in': positions}
        if not providers_ids and self.for_providers:
            providers_ids = self._get_filtered_providers(
                providers_ids,
                delivery_keys=delivery_keys
            )
        if not providers_ids:
            raise ValidationError('Получатели не найдены')
        query.update({'provider._id': {'$in': providers_ids}})
        return query, providers_ids

    @lru_cache(maxsize=5)
    def get_for_tenants_data(self, delivery=False):
        """
        Отдает запрос для получения жителей и список домов. Также
        используется при создании рассылки новостей (аргумент delivery).
        """
        providers_ids, houses = self._binds['pr'] or (), self.houses or ()
        date_tomorrow = datetime.datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0) + relativedelta(days=1)
        query = {
            '_type': 'Tenant',
            '$or': [
                {'statuses.accounting.date_till': None},
                {'statuses.accounting.date_till': {'$gte': date_tomorrow}}
            ]
        }
        if not delivery:
            query.update(
                {
                    '$and': [
                        {
                            '$or': [
                                {'telegram_chats.chat_id': {'$exists': True}},
                                {'email': {'$nin': [None, '']}}
                            ],
                        },
                        {
                            '$or': query.pop('$or')
                        }
                    ]
                },
            )

        if houses and DEFAULT_HOUSE not in houses:
            query.update({'area.house._id': {'$in': houses}})
            if delivery:
                return query, ()
        elif self.fiases and DEFAULT_FIAS not in self.fiases and providers_ids:
            houses_filter = tuple(
                chain(*(get_binded_houses(p) for p in providers_ids))
            )
            houses = House.objects(
                id__in=houses_filter,
                fias_addrobjs__in=self.fiases
            ).distinct('id')
            query.update({'area.house._id': {'$in': houses}})
            if delivery:
                return query, ()
        else:
            if not providers_ids:
                if delivery:
                    return query, ()
                providers_ids = self._get_filtered_providers()
            houses = tuple(
                chain(*(get_binded_houses(p) for p in providers_ids))
            )
            query.update({'area.house._id': {'$in': houses}})
        return query, houses

    @lru_cache(maxsize=2)
    def _get_filtered_providers(self, providers_ids=None, delivery_keys=()):
        if not providers_ids:
            providers_ids = get_crm_client_ids()
        query = {'_id': {'$in': providers_ids}}
        if delivery_keys and DEFAULT_DELIVERY_KEY not in delivery_keys:
            query.update({'delivery_keys': {'$in': delivery_keys}})
        providers = Provider.objects(__raw__=query).distinct('id')
        return tuple(providers)

    @classmethod
    def get_news_query(cls, auth, account, provider_id):
        """
        Метод, который, в зависимости от типа account-а, формирует запрос в News
        :param auth: RequestAuth
        :param account: аккаунт из сессии
        :param provider_id: _id организации
        :return: Q - запрос
        """
        if not account:
            return BindsPermissions(pr=provider_id)
        if 'Tenant' in account._type:
            house = House.objects(
                id=account.area.house.id
            ).only('id', 'fias_addrobjs').first()
            binds = BindsPermissions(pr=account.udo_provider.id)
            query = (
                (
                    cls.get_binds_query(binds)
                    | Q(**{'_binds__pr': []})
                )
                & Q(
                    is_published=True,
                    for_tenants=True,
                )
                & (
                    Q(
                        houses__in=(house.id, DEFAULT_HOUSE),
                    )
                    | Q(
                        fiases__in=house.fias_addrobjs + [DEFAULT_FIAS],
                    )
                )
            )
        else:
            binds = auth.get_binds()
            positions = [DEFAULT_POSITION]
            binds_query = cls.get_binds_query(binds, raw=True)
            position_binds = binds_query.get('_binds.po')
            if position_binds:
                positions.append(position_binds)
            provider_binds = Q(**{'_binds__pr': binds_query.get('_binds.pr')})
            # Запрос, получающий системные новости (от суперов ЗАО)
            by_supers_news_query = (
                Q(is_published=True)
                &
                Q(for_providers=True)
                &
                (
                    provider_binds | Q(_binds__pr=[])
                )
                &
                Q(_binds__po__in=positions)
            )
            # Запрос, получающий новости текущего провайдера
            provider_news_query = Q(for_tenants=True) & provider_binds
            query = (provider_news_query | by_supers_news_query)
        return query

    @classmethod
    def filter_news_by_delivery_keys(cls, news_queryset, provider_id):
        """
        Метод, который дополнительно фильтрует полученные новости для
        сотрудников по совпадению delivery_keys организации и новости.
        :param news_queryset: News.objects(query)
        :param provider_id: _id организации
        :return: отфильтрованный news_queryset
        """
        provider = Provider.objects(id=provider_id).only('delivery_keys').get()
        provider_delivery_keys = provider.delivery_keys
        # Обработка случая, когда ключи рассылки у организации не указаны
        if not provider_delivery_keys:
            filter_query = {
                '$or': [
                    {'delivery_keys': DEFAULT_DELIVERY_KEY},
                    {'delivery_keys': []}
                ]
            }
            return news_queryset.filter(__raw__=filter_query)
        provider_delivery_keys.append(DEFAULT_DELIVERY_KEY)
        provider_delivery_keys = set(provider_delivery_keys)
        provider_delivery_keys = list(provider_delivery_keys) + [[], None]
        filter_query = {'delivery_keys': {'$in': provider_delivery_keys}}
        return news_queryset.filter(__raw__=filter_query)


class NewsRead(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'NewsRead'
    }
    date = DateTimeField()
    account = ObjectIdField()
    news = ObjectIdField()
