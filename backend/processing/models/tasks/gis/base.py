import logging
from datetime import datetime
import uuid

from mongoengine import ListField, ReferenceField, FileField, DateTimeField, StringField, \
    ObjectIdField

from lib.gridfs import put_file_to_gridfs
from processing.models.tasks.base import Task, RequestTask, ZipSiblingsFilesTask, TaskStatus

from processing.models.logging.gis_log import GisImportStatus


logger = logging.getLogger('c300')


class GisBaseExportRequest(RequestTask):
    DESCRIPTION = 'ГИС. Запрос на экспорт'

    # NOTE Тут организация нужна не только для прав, по ней определяются документы начислений
    provider = ReferenceField('processing.models.billing.provider.Provider', verbose_name="Организация", required=True)
    date = DateTimeField(required=True)
    files = ListField(FileField(db_alias='files-db'))
    zip_file_name = StringField(verbose_name="Имя файла архива")
    template = FileField(db_alias='files-db', verbose_name="Шаблон для заполнения")

    def get_tasks(self):
        raise NotImplementedError('GisXLSXExportRequestTask is an abstract class')

    def get_zip_file_name(self):
        raise NotImplementedError('GisXLSXExportRequestTask is an abstract class')

    def process(self):
        logger.info('Task %s processing started', self.id)
        self.status = TaskStatus.WORK_IN_PROGRESS
        self.started = datetime.now()
        self.save()

        # CRUTCH mongoengine id reference fix
        self.provider.pk = self.provider.id
        # CRUTCH END

        Task.objects.insert(self.get_tasks())

        self.create_child_task(
            ZipSiblingsFilesTask,
            filename=self.get_zip_file_name(),
            provider=self.provider  # TODO убрать после реализации прав (заменить на наследование прав от реквеста)
        ).save()

        self.status = TaskStatus.DONE
        self.ended = datetime.now()
        self.save()
        logger.info('Task %s processing finished', self.id)


class GisBaseExportTask(Task):
    DESCRIPTION = 'ГИС. Задача экспорта'

    filename = StringField(verbose_name="Имя создаваемого файла")
    file_uuid = StringField(verbose_name="UUID создаваемого файла")
    # file = FileField(db_alias='files-db')
    file = ObjectIdField()

    # TODO убрать после реализации прав (заменить на наследование прав от реквеста)
    # Сейчас добавлено для фильтрации задач по организации, от которой производится запрос
    provider = ReferenceField('processing.models.billing.provider.Provider', verbose_name="Организация", required=True)

    PRODUCER_CLS = None

    def get_entries(self):
        raise NotImplementedError()

    def process(self):
        logger.info('Task %s processing started', self.id)
        self.status = TaskStatus.WORK_IN_PROGRESS
        self.started = datetime.now()
        self.save()

        try:
            xlsx = self.PRODUCER_CLS(self.get_entries()).get_xlsx_pyoo(self)
        except Exception as error:
            GisImportStatus(  # сохраняем ошибку
                task=self.parent.id,  # export_task.parent.id
                description=str(error),
                is_error=True, status='ошибка',
            ).save()

            self.status = TaskStatus.ERROR  # сохраняем данные задачу
            self.ended = datetime.now()
            self.save()
            raise  # пробрасываем исключение (завершаем задачу)

        self.file_uuid = uuid.uuid4().hex
        logger.info('Task %s putting file', self.id)
        self.file = put_file_to_gridfs(
            'Provider',
            self.parent.provider.id,
            xlsx,
            uuid=self.file_uuid,
            filename=self.filename,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        self.status = TaskStatus.DONE
        self.ended = datetime.now()
        self.save()
        logger.info('Task %s processing finished', self.id)


class GisBaseImportRequest(RequestTask):
    DESCRIPTION = 'ГИС. Запрос на импорт'

    IMPORT_TASK_CLS = None

    import_files = ListField(ObjectIdField())

    # TODO убрать после реализации прав (заменить на наследование прав от реквеста)
    # Сейчас добавлено для фильтрации задач по организации, от которой производится запрос
    provider = ReferenceField('processing.models.billing.provider.Provider', verbose_name="Организация", required=True)

    def process(self, *args, **kwargs):
        self.status = TaskStatus.WORK_IN_PROGRESS
        self.started = datetime.now()
        self.save()

        for file in self.import_files:
            self.create_child_task(
                self.IMPORT_TASK_CLS,
                import_file=file,
                provider=self.provider  # TODO убрать после реализации прав (заменить на наследование прав от реквеста)
            ).save()

        self.status = TaskStatus.DONE
        self.ended = datetime.now()
        self.save()


class GisBaseImportTask(Task):
    DESCRIPTION = 'ГИС. Задача импорта'

    IMPORTER_CLS = None
    START_ROW = 3

    import_file = ObjectIdField()

    # TODO убрать после реализации прав (заменить на наследование прав от реквеста)
    # Сейчас добавлено для фильтрации задач по организации, от которой производится запрос
    provider = ReferenceField('processing.models.billing.provider.Provider', verbose_name="Организация", required=True)

    def process(self):
        self.status = TaskStatus.WORK_IN_PROGRESS
        self.started = datetime.now()
        self.save()

        from processing.models.billing.provider.main import Provider
        self.provider = Provider.objects(pk=self.provider.pk).get()

        from processing.data_importers.gis.base import BaseGISDataImporter
        importer: BaseGISDataImporter = self.IMPORTER_CLS()

        if importer.USE_OPENPYXL:
            importer.import_xlsx_openpyxl(self)
        else:
            importer.import_xlsx_pyoo(self)

        self.status = TaskStatus.DONE
        self.ended = datetime.now()
        self.save()
