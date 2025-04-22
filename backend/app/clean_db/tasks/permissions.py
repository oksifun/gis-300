import datetime

from app.celery_admin.workers.config import celery_app


@celery_app.task(
    soft_time_limit=6 * 60 * 60,
    bind=True
)
def find_and_clean_unused_house_group(self, provider_id=None):
    from processing.models.billing.house_group import HouseGroup
    from processing.models.billing.provider.main import Provider
    from app.personnel.models.personnel import Worker
    match = dict(hidden=True)
    if provider_id:
        match.update(provider=provider_id)
    house_groups = HouseGroup.objects(
        **match,
    ).only(
        'id',
        'provider',
    ).as_pymongo()
    for house_group in house_groups:
        hg_id = house_group['_id']
        provider = Provider.objects(
            pk=house_group['provider'],
        ).only(
            'id',
            '_binds_permissions',
        ).as_pymongo().first()
        if not provider:
            cleaned = HouseGroup.clean_group_from_data(hg_id)
            HouseGroup.objects(pk=hg_id).delete()
            return f'cleaned {cleaned} of {hg_id}'
        if (
                provider.get('_binds_permissions')
                and provider['_binds_permissions'].get('hg')
                and provider['_binds_permissions']['hg'] == hg_id
        ):
            continue
        worker = Worker.objects(
            provider__id=provider['_id'],
            _binds_permissions__hg=hg_id
        ).only(
            'id',
        ).as_pymongo().first()
        if worker:
            continue
        cleaned = HouseGroup.clean_group_from_data(hg_id)
        HouseGroup.objects(pk=hg_id).delete()
        if cleaned == 0:
            continue
        now_hour = datetime.datetime.now().hour
        if now_hour < 7 or now_hour > 19:
            find_and_clean_unused_house_group.delay(provider_id=provider_id)
        return f'cleaned {cleaned} of {hg_id}'
    return 'nothing found'
