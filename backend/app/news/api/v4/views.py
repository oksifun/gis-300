from datetime import datetime

from django.utils.timezone import now as tznow
from dateutil.relativedelta import relativedelta
from django.http import JsonResponse, HttpResponse, HttpResponseNotFound

from api.v4.authentication import RequestAuth
from api.v4.base_crud_filters import LimitFilterBackend
from api.v4.permissions import IsAuthenticated
from api.v4.serializers import json_serializer, PrimaryKeySerializer
from api.v4.universal_crud import BaseCrudViewSet, ModelFilesViewSet
from api.v4.viewsets import BaseLoggedViewSet
from app.messages.models.messenger import UserTasks
from app.news.api.v4.serializers import NewsSerializer, NewsCreateSerializer, \
    NewsDailyReportSerializer, NewsMarkReadSerializer, NewsUnreadSerializer
from app.news.models.news import News, NewsRead, DEFAULT_POSITION, \
    DEFAULT_HOUSE, DEFAULT_FIAS, DEFAULT_DELIVERY_KEY
from processing.models.billing.house_group import HouseGroup


class NewsViewSet(BaseCrudViewSet):
    serializer_classes = {
        'create': NewsCreateSerializer,
        'retrieve': NewsSerializer,
        'list': NewsSerializer,
        'partial_update': NewsCreateSerializer
    }
    filter_backends = (
        LimitFilterBackend,
    )
    permission_classes = (IsAuthenticated, )

    def get_serializer_class(self):
        return self.serializer_classes[self.action]

    def get_queryset(self):
        auth = RequestAuth(self.request)
        slave_session = auth.is_slave()
        if auth.is_super() and not slave_session:
            return News.objects().order_by('-created_at')
        account, provider_id = auth.get_super_account(), auth.get_provider_id()
        query = News.get_news_query(auth, account, provider_id)
        news = News.objects(query).order_by('-created_at')
        if 'Tenant' not in account._type:
            news = News.filter_news_by_delivery_keys(news, provider_id)
        return news


class NewsCrudViewSet(NewsViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete']
    slug = 'news_list'

    def create(self, request, *args, **kwargs):
        auth = RequestAuth(request)
        account = auth.get_super_account()
        provider = auth.get_provider_id()
        request.data['author'] = {'id': account.id, 'provider': provider}
        request.data['_binds'] = self._get_filter_binds(
            request.data, account, auth
        )
        request.data['houses'] = self._get_houses(request.data, auth)
        request.data['fiases'] = self._get_fiases(request.data)
        request.data['delivery_keys'] = self._get_delivery_keys(request.data)
        return super().create(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        auth = RequestAuth(request)
        account = auth.get_super_account()
        fields = {
            'providers', 'houses', 'fiases', 'position_codes', 'delivery_keys'
        }
        request_fields = set(request.data.keys())
        if fields.issubset(request_fields):
            request.data['_binds'] = self._get_filter_binds(
                request.data, account, auth
            )
            request.data['houses'] = self._get_houses(request.data, auth)
            request.data['delivery_keys'] = self._get_delivery_keys(
                request.data
            )
        return super().partial_update(request, *args, **kwargs)

    @staticmethod
    def _get_houses(data, auth):
        houses = data.get('houses')
        if data.get('for_tenants') and not data.get('for_providers'):
            if not houses and not data.get('fiases'):
                binds = auth.get_binds()
                if (binds and binds.hg) or auth.is_slave():
                    house_groups = HouseGroup.objects(
                        pk=binds.hg
                    ).only(
                        'houses'
                    ).as_pymongo().get()
                    return house_groups['houses']
                else:
                    return [DEFAULT_HOUSE]
            else:
                return houses
        else:
            return []

    @staticmethod
    def _get_fiases(data):
        fiases = data.get('fiases')
        if data.get('for_tenants'):
            if not fiases and not data.get('houses'):
                return [DEFAULT_FIAS]
            else:
                return fiases
        else:
            return []

    @staticmethod
    def _get_delivery_keys(data):
        delivery_keys = data.get('delivery_keys')
        if data.get('for_providers'):
            if not delivery_keys:
                return [DEFAULT_DELIVERY_KEY]
            else:
                return delivery_keys
        else:
            return []

    @staticmethod
    def _get_filter_binds(data, account, auth):
        # "providers" и "position_codes" отправляются всегда: либо со
        # значениями, указанными пользователем, либо пустым списком.
        providers = data.get('providers')
        # Если "position_codes" отправлен пустым списком, то такая
        # новость создана супер-пользователем для всех или сотрудником
        # организации, который не имеет возможности указать такой параметр.
        positions = data.get('position_codes') or [DEFAULT_POSITION]
        # Если новость опубликована супер-пользователем под внешним управлением
        # или сотрудником, то необходимо изменить провайдера на того, под
        # которым сейчас внешнее управление/сотрудник.
        if auth.is_slave() or not auth.is_super():
            providers = [auth.get_provider_id()]
        binds = {
            'pr': providers,
            'po': positions
        }
        return binds


class NewsHeadImgViewSet(ModelFilesViewSet):
    model = News
    slug = 'news_list'


class NewsFilesViewSet(ModelFilesViewSet):
    model = News
    slug = 'news_list'

    def retrieve(self, request, pk):
        pk = PrimaryKeySerializer.get_validated_pk(pk)
        file_id = PrimaryKeySerializer.get_validated_pk(
            request.query_params.get('file')
        )
        model = self.model.objects(
            is_deleted__ne=True,
            id=pk,
        ).as_pymongo().first()
        self.parse_file(model, file_id)
        if not self.flag:
            return HttpResponseNotFound()

        return self.file_response(file_id, clear=False)


class NewsMarkReadViewSet(NewsViewSet):
    http_method_names = ['get']
    serializer_class = NewsMarkReadSerializer

    def retrieve(self, request, *args, **kwargs):
        news_id = kwargs['id']
        serializer = self.serializer_class(data={'id': news_id})
        serializer.is_valid(raise_exception=True)
        auth = RequestAuth(request)
        account = auth.get_super_account()
        NewsRead.objects(
            account=account.id,
            news=news_id
        ).upsert_one(
            account=account.id,
            news=news_id,
            date=tznow()
        )
        return HttpResponse(f"{news_id} marked as read")


class NewsUnreadViewSet(NewsViewSet):
    serializer_class = NewsUnreadSerializer

    def list(self, request, *args, **kwargs):
        auth = RequestAuth(request)
        account = auth.get_super_account()
        if account.get_access_date:
            query = {'created_at': {'$gte': account.get_access_date}}
        else:
            query = {
                'created_at': {'$gt': datetime(2017, 4, 5)}
            }
        news_read = tuple(n.news for n in NewsRead.objects(account=account.id))
        query.update({'_id': {'$nin': news_read}, 'author.id': {'$ne': account.id}})
        news_unread = self.get_queryset().filter(__raw__=query)
        data = NewsUnreadSerializer(news_unread, many=True).data
        if not data:
            UserTasks.objects(account=account.id).update(unset__news=1)
        return JsonResponse(
            data=dict(results=data),
            json_dumps_params={'default': json_serializer}
        )


class NewsDailyReportViewSet(BaseLoggedViewSet):
    slug = 'news_list'

    def list(self, request):
        serializer = NewsDailyReportSerializer(data=request.query_params)
        serializer.is_valid()
        data = serializer.validated_data
        news_read = list(NewsRead.objects.aggregate(*self._get_pipeline(data)))
        d = data.get('date_from')
        ix = 0
        while ix < len(news_read):
            current_date = news_read[ix]['datetime']
            while d < current_date:
                news_read.insert(ix, {'datetime': d, 'count': 0, 'tenants': 0})
                d += relativedelta(days=1)
                ix += 1
            d += relativedelta(days=1)
            ix += 1
        while d <= data.get('date_till'):
            news_read.insert(ix, {'datetime': d, 'count': 0, 'tenants': 0})
            d += relativedelta(days=1)
            ix += 1
        return JsonResponse(
            data=dict(results=news_read),
            json_dumps_params={'default': json_serializer}
        )

    @staticmethod
    def _get_pipeline(data):
        return [
            {'$match': {
                'news': data.get('news_id'),
                'date': {
                    '$gte': data.get('date_from'),
                    '$lt': data.get('date_till') + relativedelta(days=1)
                },
            }},
            {'$project': {
                'day': {'$dateToString': {
                    'format': '%d.%m.%Y',
                    'date': '$date'
                }},
                'date': 1,
                'account': 1,
            }},
            {'$lookup': {
                'from': 'Account',
                'localField': 'account',
                'foreignField': '_id',
                'as': 'account',
            }},
            {'$unwind': '$account'},
            {'$unwind': '$account._type'},
            {'$match': {'account._type': {'$in': ['Tenant', 'Worker']}}},
            {'$project': {
                'day': 1,
                'date': 1,
                'tenant': {'$cond': [
                    {'$eq': ['$account._type', 'Tenant']},
                    {'$literal': 1},
                    {'$literal': 0},
                ]},
            }},
            {'$group': {
                '_id': '$day',
                'count': {'$sum': 1},
                'tenants': {'$sum': '$tenant'},
                'order_date': {'$first': '$date'}
            }},
            {'$sort': {'order_date': 1}},
            {'$project': {
                'date': '$_id',
                'count': 1,
                'tenants': 1,
                'datetime': '$order_date'
            }}
        ]

