from bson import ObjectId

from app.gis.services.contracts import ManagementContracts
from app.gis.workers.config import gis_celery_app


@gis_celery_app.task(name='gis.import_provider_documents')
def import_provider_documents(provider_id: ObjectId, house_id: ObjectId):
    """
    Загрузка из ГИС ЖКХ устава (договора) управляющей домом организации
    """
    _export = ManagementContracts.exportCAChData(provider_id, house_id)

    _export.approved()  # утвержденный ДУ (устав) дома


@gis_celery_app.task(name='gis.export_provider_documents')
def export_provider_documents(provider_id: ObjectId, house_id: ObjectId):
    """
    TODO Выгрузка в ГИС ЖКХ устава управляющей организации
    """
    _import = ManagementContracts.importCharterData(provider_id, house_id)

    _import()  # TODO определенный устав или ДУ?


if __name__ == '__main__':

    from mongoengine_connections import register_mongoengine_connections
    register_mongoengine_connections()

    p = ObjectId("54d9d64ff3b7d4398079309d")

    h = ObjectId("6478ada6ba50060019a39b1d")  # TODO в случае нескольких домов
    from app.gis.utils.houses import get_provider_house
    h = get_provider_house(p, h, abort_failed=True)

    import_provider_documents(p, h); exit()
    # export_provider_documents(p, h); exit()  # WARN
