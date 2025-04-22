from app.caching.models.compendium import CompendiumBindsTask
from app.catalogue.models.compendium import CompendiumService, \
    CompendiumProviderBinds
from app.celery_admin.workers.config import celery_app
from app.caching.tasks.cache_update import total_seconds
from settings import ZAO_OTDEL_PROVIDER_OBJECT_ID


@celery_app.task(
    bind=True,
    rate_limit="100/m",
    max_retries=3,
    soft_time_limit=total_seconds(seconds=60),
)
def create_compendium_provider_binds(self, provider_id, task_id):
    CompendiumBindsTask.set_wip_state(task_id)
    hide_service_ids = CompendiumService.objects(
        provider__id=ZAO_OTDEL_PROVIDER_OBJECT_ID,
        is_hide_service=True,
        is_deleted__ne=True,
    ).distinct('id')
    binds = CompendiumProviderBinds(
        provider=provider_id,
        compendium_service_hide=hide_service_ids,
    )
    binds.save()
    CompendiumBindsTask.set_success_state(task_id)

