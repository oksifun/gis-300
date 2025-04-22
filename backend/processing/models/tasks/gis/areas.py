from processing.models.tasks.gis.base import GisBaseImportRequest, \
    GisBaseImportTask
from processing.data_importers.gis.areas import AreasIdsDataImporter


class AreasIdsImportTask(GisBaseImportTask):
    DESCRIPTION = getattr(GisBaseImportTask, 'DESCRIPTION') + ': ЛС'

    IMPORTER_CLS = AreasIdsDataImporter
    START_ROW = 3


class AreasIdsImportRequest(GisBaseImportRequest):
    DESCRIPTION = getattr(GisBaseImportRequest, 'DESCRIPTION') + ': ЛС'

    IMPORT_TASK_CLS = AreasIdsImportTask


if __name__ == '__main__':

    from mongoengine_connections import register_mongoengine_connections
    register_mongoengine_connections()

    from bson import ObjectId

    # i = ObjectId("643e9764b5f98100116959d3")
    # r: AreasIdsImportRequest = AreasIdsImportRequest.objects.with_id(i)
    # r.process()

    i = ObjectId("643e9ab28b65305bd469c411")
    t: AreasIdsImportTask = AreasIdsImportTask.objects.with_id(i)
    t.process()
