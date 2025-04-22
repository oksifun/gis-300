from bson import ObjectId

from api.v4.utils import import_from_string
from app.celery_admin.workers.config import celery_app
from app.house.models.house import House
from app.news.models.cached_news import CachedNews, NewsEmbedded
from app.personnel.models.personnel import Worker
from lib.dates import total_seconds
from processing.models.billing.account import Tenant
from processing.models.billing.provider.main import Provider


@celery_app.task(
    bind=True,
    rate_limit="100/s",
    max_retries=7,
    soft_time_limit=total_seconds(seconds=180),
    default_retry_delay=30
)
def recalculate_statistics(self, news_id, created=False):
    """(Пере)расчет статистики новости на основе ее привязок."""
    News_ = import_from_string('app.news.models.news.News')
    NewsStatistics_ = import_from_string('app.news.models.news.NewsStatistics')

    news = News_.objects(id=news_id).get()
    providers_ids, workers, tenants_count, houses = (), (), 0, ()

    if news.for_providers:
        query, providers_ids = news.get_for_providers_data()
        workers = tuple(
            (w['id'], w['email'])
            for w in Worker.objects(__raw__=query).only('email')
        )
    if news.for_tenants:
        query, houses = news.get_for_tenants_data()
        tenants = Tenant.objects(__raw__=query)
        tenants_count = tenants.count()

    if created:
        workers_email = 0
    else:
        workers_email = len(tuple(w[1] for w in workers if w[1]))
    statistics_dict = dict(
        providers=len(providers_ids),
        workers_access=len(workers),
        workers_email=workers_email,
        tenants=tenants_count,
        houses=len(houses)
    )
    statistics = NewsStatistics_(**statistics_dict)
    news.update(statistics=statistics)
    return statistics_dict


def _get_houses(houses, fiases):
    if houses:
        return houses
    else:
        return [h['_id'] for h in
                House.objects(fias_addrobjs__in=fiases).as_pymongo()]


def add(news_id, news_obj, houses):
    """
    Метод для добавления новости домам из списка
    """
    author_provider_name = None
    if news_obj.author.provider:
        provider = Provider.objects(
            id=news_obj.author.provider
        ).only('str_name').get()
        author_provider_name = provider.str_name
    news_dict = dict(
        _id=news_id,
        created_at=news_obj.created_at,
        head_img=news_obj.head_img,
        subject=news_obj.subject,
        body=news_obj.body,
        files=news_obj.files,
        author_provider_name=author_provider_name
    )
    news_embedded_obj = NewsEmbedded(**news_dict)
    exist = [h.house for h in
             CachedNews.objects(house__in=houses).only('house')]
    if exist:
        # добавление новости для домов, у которых уже есть записи в кэше
        CachedNews.objects(house__in=exist).update(push__news__0=news_dict)
    houses = set(houses) - set(exist)
    new_objs = list()
    for house in houses:
        obj = CachedNews(house=house, news=[news_embedded_obj])
        new_objs.append(obj)
    if new_objs:
        CachedNews.objects().insert(new_objs)


def update(news_id, news_obj, houses):
    """
    Метод для обновления новости у всех домов из списка
    """
    # ищем новость у всех домов
    cache = CachedNews.objects(__raw__={'news._id': news_id}).all()
    cached_houses = []
    for item in cache:
        cached_houses.append(item.house)
    houses_to_add = list(set(houses) - set(cached_houses))
    houses_to_delete = list(set(cached_houses) - set(houses))
    houses_to_update = list(set(houses) & set(cached_houses))
    if houses_to_add:
        # если новость убрали из тех домов, у которых она была и
        # добавили в другие
        add(news_id, news_obj, houses_to_add)
    if houses_to_delete:
        delete(news_id, houses_to_delete)
    if houses_to_update:
        news_query = {'news._id': news_id, 'house': {'$in': houses_to_update}}
        CachedNews.objects(__raw__=news_query).update(
            set__news__S__created_at=news_obj.created_at,
            set__news__S__head_img=news_obj.head_img,
            set__news__S__subject=news_obj.subject,
            set__news__S__body=news_obj.body,
            set__news__S__files=news_obj.files
        )


def delete(news_id, houses=None):
    """
    Метод для удаления новости у домов из списка
    """
    query = {'news._id': news_id}
    if houses:
        query.update({'house': {'$in': houses}})
    CachedNews.objects(__raw__=query).update(
        __raw__={
            '$pull': {
                'news': {'_id': news_id}
            }
        }
    )


@celery_app.task(
    bind=True,
    rate_limit="100/s",
    max_retries=7,
    soft_time_limit=total_seconds(seconds=180),
    default_retry_delay=30
)
def update_house_news(self, news_obj, method):
    """
    Функция для обновления списка новостей дома для ЛКЖ
    :param self: объект Celery Task
    :param news_obj: объект News
    :param method: add/delete добавить или удалить новость из кэша
    :return: None
    """
    houses = _get_houses(news_obj.houses, news_obj.fiases)
    if not houses:
        return
    news_id = ObjectId(news_obj.id)
    if method == 'add':
        add(news_id, news_obj, houses)
    elif method == 'delete':
        delete(news_id)
    else:
        update(news_id, news_obj, houses)
