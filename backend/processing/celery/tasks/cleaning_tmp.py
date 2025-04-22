import datetime

from dateutil.relativedelta import relativedelta

from app.caching.models.filters import FilterCache, FilterPreparedData
from app.celery_admin.workers.config import celery_app


@celery_app.task(
    soft_time_limit=2 * 60,
    bind=True
)
def clean_filters_cash(self):
    """
    Чистка кэша фильтров. Кэш хранится не более 60 минут с момента последнего
    использования, а данные не более 10 и не более 30 минут с момента создания
    """
    arc_date = datetime.datetime.now() - relativedelta(minutes=60)
    filters_deleted = FilterCache.objects.filter(
        used__lt=arc_date,
    ).delete()
    arc_date = datetime.datetime.now() - relativedelta(minutes=10)
    filters_data_deleted = FilterPreparedData.objects.filter(
        used__lt=arc_date,
    ).delete()
    arc_date = datetime.datetime.now() - relativedelta(minutes=30)
    filters_data_deleted += FilterPreparedData.objects.filter(
        created__lt=arc_date,
    ).delete()
    return 'Deleted filters {}, data {}'.format(
        filters_deleted,
        filters_data_deleted,
    )
