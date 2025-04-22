from processing.models.billing.responsibility import Responsibility
from app.area.models.area import Area
from processing.models.billing.provider.main import Provider
import datetime
from bson import ObjectId
from mongoengine import Q
from lib.type_convert import str_to_bool
from processing.models.billing.account import Tenant
from processing.models.billing.embeddeds.tenant import \
    DenormalizedTenantWithName
from processing.models.logging.custom_scripts import CustomScriptData


def sync_responsibilities(logger, task, house_id, provider_from_id,
                          provider_to_id):
    CustomScriptData(
        task=task.id if task else None,
        coll='Responsibility',
        data=list(Responsibility.objects(provider=provider_to_id).as_pymongo()),
    ).save()
    areas = Area.objects(house__id=house_id)
    logger(f'Нашла {areas.count()}')
    Responsibility.sync_by_areas(
        areas,
        Provider.objects(id=provider_from_id).get(),
        Provider.objects(id=provider_to_id).get(),
    )
    logger('Завершено')


def mark_responsibles_by_filter(logger, task, house_id, provider_id, date_from,
                                only_developer=False, name_contains=None):
    """
    Проставляет ответственность в доме по отношению к переданной организации
    :param logger:
    :param task:
    :param house_id: дом
    :param provider_id: организация
    :param date_from: начиная с даты
    :param only_developer: только для ЛС застройщика
    :param name_contains: для существ, содержащих эту строку в имени
    :return:
    """
    if isinstance(date_from, str):
        date_from = datetime.datetime.strptime(date_from, '%d.%m.%Y')
    provider_id = ObjectId(provider_id)
    house_id = ObjectId(house_id)
    CustomScriptData(
        task=task.id if task else None,
        coll='Responsibility',
        data=list(
            Responsibility.objects(
                account__area__house__id=house_id,
            ).as_pymongo(),
        ),
    ).save()
    query = Q(area__house__id=house_id)
    if str_to_bool(only_developer):
        query &= Q(is_developer=True)
    if name_contains:
        query &= Q(str_name__contains=name_contains)
    provider = Provider.objects(pk=provider_id).get()
    query &= Tenant.get_binds_query(provider._binds_permissions)
    tenants = Tenant.objects(query).distinct('id')
    logger(f'Нашла жителей {len(tenants)} всего')
    responsible = Responsibility.get_accounts(provider_id, house_id, date_from)
    tenants = set(tenants) - set(responsible)
    logger(f'из них безответственных {len(tenants)}')
    for tenant_id in tenants:
        Responsibility(
            account=DenormalizedTenantWithName(id=tenant_id),
            provider=provider_id,
            date_from=date_from,
        ).save()
    logger('Завершено')
