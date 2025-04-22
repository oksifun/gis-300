from mongoengine import ListField, EmbeddedDocumentField

from app.caching.models.denormalization import DenormalizationTask
from app.caching.tasks.cache_update import total_seconds
from app.celery_admin.workers.config import celery_app
from processing.models.denormalizing_schema import DENORMALIZING_SCHEMA
from utils.crm_utils import provider_can_tenant_access


@celery_app.task(
    bind=True,
    rate_limit="100/m",
    max_retries=3,
    soft_time_limit=total_seconds(seconds=60),
)
def denormalize_provider_to_cabinets(self, provider_id, task_id=None):
    if task_id:
        DenormalizationTask.set_wip_state(task_id)
    from processing.models.billing.provider.main import Provider
    from app.auth.models.actors import Actor
    provider = Provider.objects(
        pk=provider_id,
    ).only(
        'str_name',
        'inn',
    ).get()
    cabinet_access = provider_can_tenant_access(provider_id)
    Actor.objects(
        provider__id=provider_id,
    ).update(
        provider__client_access=cabinet_access,
        provider__str_name=provider.str_name,
        provider__inn=provider.inn,
    )
    if task_id:
        DenormalizationTask.set_success_state(task_id)


@celery_app.task(
    bind=True,
    rate_limit="100/m",
    max_retries=3,
    soft_time_limit=total_seconds(seconds=60),
)
def denormalize_house_sectors_to_cabinets(self, house_id, task_id):
    DenormalizationTask.set_wip_state(
        task_id,
        self.soft_time_limit if self else None,
    )
    from app.auth.models.actors import Actor
    from app.house.models.house import House
    from app.area.models.area import Area
    house = House.objects(pk=house_id).get()
    actor_sectors = house.get_sectors_by_area_ranges()
    Actor.objects(
        owner__house__id=house_id,
    ).update(
        sectors=[],
    )
    updated = 0
    for areas, sectors in actor_sectors.items():
        query = house.parse_areas_range_to_query(areas)
        query['house._id'] = house_id
        bound_areas = [
            area['_id']
            for area in Area.objects(__raw__=query).only('id').as_pymongo()
        ]
        if not bound_areas:
            continue
        updated += Actor.objects(
            owner__house__id=house_id,
            owner__area__id__in=bound_areas,
        ).update(
            add_to_set__sectors=list(sectors),
        )
    DenormalizationTask.set_success_state(task_id)
    return f'updated {updated}'


@celery_app.task(
    bind=True,
    rate_limit="100/m",
    max_retries=3,
    soft_time_limit=total_seconds(seconds=60),
)
def sync_provider_permissions_to_cabinets(self, provider_id, task_id=None):
    if task_id:
        base_task = DenormalizationTask.objects(pk=task_id).first()
    else:
        base_task = DenormalizationTask.objects(
            obj_id=provider_id,
            func_name='sync_provider_permissions_to_cabinets',
        ).first()
    if base_task:
        DenormalizationTask.set_wip_state(
            base_task.id,
            self.soft_time_limit if self else None,
        )
    from app.auth.models.actors import Actor
    houses = Actor.objects(
        owner__owner_type='Tenant',
        provider__id=provider_id,
        _type='Actor',
    ).distinct(
        'owner.house.id',
    )
    for house in houses:
        task = DenormalizationTask(
            model_name='RoboActor',
            field_name='permissions',
            obj_id=provider_id,
            func_name='denormalize_provider_permission_to_cabinets',
            kwargs={
                'house_id': house,
                'provider_id': provider_id,
            },
        )
        task.save()
        denormalize_provider_permission_to_cabinets.delay(
            provider_id,
            house,
            task.id,
        )
    if base_task:
        DenormalizationTask.set_success_state(base_task.id)


_ONLY_READ_PERMISSION = 2


@celery_app.task(
    bind=True,
    rate_limit="100/m",
    max_retries=3,
    soft_time_limit=total_seconds(seconds=60),
)
def denormalize_provider_permission_to_cabinets(self, provider_id, house_id,
                                                task_id):
    DenormalizationTask.set_wip_state(
        task_id,
        self.soft_time_limit if self else None,
    )
    from app.auth.models.actors import Actor, RoboActor
    perms = RoboActor.get_cabinet_permissions(provider_id, house_id)
    regular_updated = Actor.objects(
        provider__id=provider_id,
        owner__house__id=house_id,
        owner__owner_type='Tenant',
        limited_access__ne=True,
    ).update(
        permissions=perms,
    )
    RoboActor.cut_cabinet_permissions_for_limited_access(perms)
    limited_updated = Actor.objects(
        provider__id=provider_id,
        owner__house__id=house_id,
        owner__owner_type='Tenant',
        limited_access=True,
    ).update(
        permissions=perms,
    )
    DenormalizationTask.set_success_state(task_id)
    return f'regular {regular_updated}, limited {limited_updated}'


def _cut_catalogue_restrictions(permissions, provider_id, house_id):
    if not (permissions['request_log'] & _ONLY_READ_PERMISSION):
        permissions.pop('catalogue_cabinet_positions')
        return
    from app.catalogue.models.catalogue import CatalogueHouseBind
    catalog_allow = CatalogueHouseBind.objects(
        house=house_id,
        provider=provider_id,
    ).as_pymongo().first()
    if not catalog_allow or not catalog_allow.get('catalog_codes'):
        permissions.pop('catalogue_cabinet_positions')
        return
    from app.catalogue.models.catalogue import Catalogue
    catalog_allow = Catalogue.objects(
        provider=provider_id,
        is_deleted__ne=True,
        public=True,
        code__in=catalog_allow['catalog_codes'],
    ).only(
        'id',
    ).as_pymongo().first()
    if not catalog_allow:
        permissions.pop('catalogue_cabinet_positions')


@celery_app.task(
    bind=True,
    rate_limit="100/m",
    max_retries=3,
    soft_time_limit=total_seconds(seconds=60),
)
def foreign_denormalize_data(self, model_from, field_name, object_id,
                             task_id=None):
    if task_id:
        DenormalizationTask.set_wip_state(
            task_id,
            self.soft_time_limit if self else None,
        )
    obj = model_from.objects(
        pk=object_id,
    ).only(
        'id',
        field_name,
    ).get()
    field_value = getattr(obj, field_name)
    schema = DENORMALIZING_SCHEMA[model_from]
    exception = None
    for model in schema:
        path = _get_path(model, model_from, field_name)
        if path:
            try:
                _update_object_field_by_path(
                    model,
                    object_id,
                    path,
                    field_name,
                    field_value,
                )
            except Exception as ex:
                exception = ex
                continue
    if exception:
        raise exception
    if task_id:
        DenormalizationTask.set_success_state(task_id)


def _update_object_field_by_path(model, obj_id, path, field_name, field_value):
    cls = _get_cls_by_path(model, path, field_name)
    if hasattr(cls, 'from_ref'):
        value = cls.from_ref(field_value)
    else:
        value = field_value
    path = '__'.join(path)
    model.objects(
        **{f'{path}__id': obj_id},
    ).update(
        **{f'set__{path}__{field_name}': value},
    )


def _get_cls_by_path(model, path, field_name):
    result = model._fields[path[0]].document_type_obj
    if len(path) > 1:
        return _get_cls_by_path(result, path[1:], field_name)
    if hasattr(result._fields[field_name], 'document_type_obj'):
        return result._fields[field_name].document_type_obj
    return result._fields[field_name]


def _get_path(model, model_from, field_name, path=None):
    result = path or []
    for name, field in model._fields.items():
        if (
                isinstance(field, ListField)
                and isinstance(field.field, EmbeddedDocumentField)
        ):
            embedded_cls = field.field.document_type_obj
        elif isinstance(field, EmbeddedDocumentField):
            embedded_cls = field.document_type_obj
        else:
            continue
        if (
                not hasattr(embedded_cls, 'DENORMALIZE_FROM')
                or embedded_cls.DENORMALIZE_FROM != model_from.__name__
        ):
            embedded_result = _get_path(
                embedded_cls,
                model_from,
                field_name,
                result + [name],
            )
            if embedded_result:
                return embedded_result
            continue
        if embedded_cls.DENORMALIZE_FROM == model_from.__name__:
            if field_name in embedded_cls._fields:
                return result + [name]
            else:
                return []
    return []
