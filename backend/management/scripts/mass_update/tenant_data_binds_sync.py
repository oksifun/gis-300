from bson import ObjectId

from processing.models.billing.account import Tenant
from processing.models.billing.tenant_data import TenantData


def run_tenant_data_sync(logger, task, house_id, provider_id=None):
    from processing.celery.tasks.dr_hugo_strange.migrations import \
        run_migration
    tenants = get_tenants_by_house_ids(house_id)
    for tenant in tenants:
        run_migration(
            func=_set_binds,
            tenant_id=tenant['_id'],
            binds=tenant['_binds'],
        )


def _set_binds(tenant_id, binds, logger=print):
    query = dict(__raw__=dict(tenant=tenant_id))
    updater = dict(set___binds=binds)
    try:
        TenantData.objects(**query).update(**updater)
    except Exception as error:
        return logger(f'Ошибка у Tenant ObjectId("{tenant_id}"): {error}')


def get_tenants_by_house_ids(house_id: ObjectId):
    return Tenant.objects(
        area__house__id=house_id,
        _type__ne='OtherTenant',
        is_deleted__ne=True
    ).only('id', '_binds').as_pymongo()
