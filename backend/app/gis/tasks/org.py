from bson import ObjectId

from app.gis.services.org_registry_common import OrgRegistryCommon as Service
from app.gis.workers.config import gis_celery_app


@gis_celery_app.task(name='gis.import_provider_data')
def import_organisation_data(provider_id: ObjectId, **options):
    """
    Загрузка из ГИС ЖКХ данных организаций
    """
    Service.exportOrgRegistry(
        provider_id, **options
    ).providers()  # поставщик информации и управляющие домами организации


@gis_celery_app.task(name='gis.import_entity_data')
def import_entity_data(provider_id: ObjectId, entity_props: dict,  **options):
    """
    Загрузка из ГИС ЖКХ данных (организации) ЮЛ
    """
    _export = Service.exportOrgRegistry(
        provider_id, **options
    )
    search_criteria: list = _export.entity_criteria(entity_props)
    _export(SearchCriteria=search_criteria)  # идентификаторы и реквизиты ЮЛ


if __name__ == '__main__':

    from mongoengine_connections import register_mongoengine_connections
    register_mongoengine_connections(secondary_prefered=True)

    p = ObjectId("526234b2e0e34c4743821eb6")

    e = {
        ObjectId("612e09a0996880000e494464"): {'ogrn': '1127847608350'},
    }  # TODO ProviderId: {'ogrn: 'ОГРН'}
    # import_entity_data(p, e); exit()

    import_organisation_data(p)
