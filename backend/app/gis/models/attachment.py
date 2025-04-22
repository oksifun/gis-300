from typing import Optional

from uuid import UUID

from bson import ObjectId
from mongoengine import DoesNotExist

from mongoengine.document import EmbeddedDocument
from mongoengine.fields import ObjectIdField, UUIDField, StringField

from gridfs import GridOut

from lib.gridfs import get_file_from_gridfs, put_file_to_gridfs

from app.gis.core.gost import calc_old_hash
from app.gis.core.exceptions import NoDataError, NoGUIDError

from app.gis.models.guid import GUID

from app.gis.services.file_store import FileStore

from app.gis.utils.common import as_guid


class Attachment(EmbeddedDocument):  # Attachment[WODescription]Type
    """Информация о вложении ГИС ЖКХ"""
    # meta = {'db_alias': 'legacy-db', 'collection': 'Attachment'}

    guid = UUIDField(primary_key=True, verbose_name="Идентификатор вложения")

    name = StringField(required=True, min_length=1, max_length=1024,
        verbose_name="Наименование вложения")
    description = StringField(max_length=500,  # required без WO
        verbose_name="Описание вложения (файловый контекст)")

    hash = StringField(required=True,  # обязателен при импорте
        verbose_name="Хэш вложения по алгоритму ГОСТ в binhex")

    provider_id = ObjectIdField(verbose_name="Идентификатор организации")

    def __hash__(self):
        """
        Функция необходима для сохранения уникальности списка вложений
        """
        from hashlib import md5
        return int(md5(str(self.guid).encode('utf-8')).hexdigest(), 16)

    @property
    def uuid(self) -> str:
        """Только значащие символы идентификатора (без -)"""
        return self.guid.hex  # 32 байта

    @property
    def as_req(self) -> dict:
        """AttachmentType"""
        attachment = {'AttachmentGUID': self.guid}  # вложенный элемент

        return {'Name': self.name, 'Description': self.description,
            'Attachment': attachment, 'AttachmentHASH': self.hash}

    @classmethod
    def from_gis(cls, provider_id: ObjectId, *attachment_s) -> list:
        """
        Создать вложения ГИС ЖКХ (EmbeddedDocument) из полученных данных

        :param provider_id: идентификатор организации
        :param attachment_s: AttachmentType
            Name, Description, Attachment.AttachmentGUID, AttachmentHASH
        """
        return [cls(
            name=file.Name, description=file.Description,
            guid=as_guid(file.Attachment.AttachmentGUID),
            hash=file.AttachmentHASH, provider_id=provider_id,
        ) for file in attachment_s]

    def save(self, resource: GUID, file_data: bytes) -> ObjectId:
        """Сохранить данные (файла) сущности ГИС ЖКХ"""
        return put_file_to_gridfs(resource.tag, resource.object_id,
            file_data, self.uuid,  # WARN при uuid=None вернет tuple
            self.name, resource.provider_id)  # возвращаем files.id

    @staticmethod
    def get_resource_guid(grid_file: GridOut) -> Optional[GUID]:
        """Получить связанные с файлом данные сущности ГИС ЖКХ"""
        if (
            hasattr(grid_file, 'owner_id') and  # GUID.object_id
            hasattr(grid_file, 'owner_resource') and  # GUID.tag
            grid_file.owner_resource in GUID.OBJECT_TAGS
        ):
            return GUID.objects(__raw__={
                'tag': grid_file.owner_resource, 'object_id': grid_file.owner_id
            }).first()
        else:  # связь файла с сущностью отсутствует!
            return None

    @classmethod
    def push(cls, file_id: ObjectId, file_context: str = None) -> 'Attachment':
        """Сохранить файл в хранилище ГИС ЖКХ и получить вложение"""
        try:
            grid_file: GridOut = get_file_from_gridfs(file_id, raw=True)
        except DoesNotExist:  # mongoengine.errors
            raise NoDataError(f"Файл с идентификатором {file_id} не найден")
        assert isinstance(grid_file, GridOut), \
            f"Получен некорректный тип {type(grid_file)} данных файла"

        guid: GUID = cls.get_resource_guid(grid_file)

        if guid is None:  # данные ГИС ЖКХ не найдены?
            raise NoDataError(f"Файл не связан с сущностью ГИС ЖКХ")
        elif not guid:  # идентификатор ГИС ЖКХ не загружен?
            raise NoGUIDError(f"Данные сущности ГИС ЖКХ не загружены")

        if hasattr(grid_file, 'uploader'):
            provider_id: ObjectId = grid_file.uploader
            assert provider_id == guid.provider_id, \
                "Файл загружен не поставщиком информации ГИС ЖКХ"
        else:
            provider_id: ObjectId = guid.provider_id
        assert provider_id, "Владеющая файлом организации не определена"

        if not file_context and hasattr(grid_file, 'owner_resource'):
            file_context = FileStore.get_gis_context(grid_file.owner_resource)

        file_data: bytes = grid_file.read()  # TODO читать частями?
        gost_hash: str = calc_old_hash(file_data)  # хэш-сумма данных

        gis_store = FileStore(provider_id, file_context)  # или по умолчанию
        upload_id: UUID = gis_store.upload_file(grid_file.filename, file_data)

        return cls(
            name=gis_store.file_name, description=gis_store.upload_context,
            guid=upload_id, hash=gost_hash, provider_id=provider_id,
        )

    @classmethod
    def pull(cls, attachment_guid: str, provider_id: ObjectId) -> 'Attachment':
        """Получить вложение ГИС ЖКХ из файлового хранилища"""
        gis_store = FileStore(provider_id)  # контекст по умолчанию

        # перед скачиваем из репозитория ГИС ЖКХ загружаются сведения о файле
        file_data: bytes = gis_store.download_file(attachment_guid)
        gost_hash: str = calc_old_hash(file_data)  # хэш-сумма данных

        return cls(
            name=gis_store.file_name, description=gis_store.upload_context,
            guid=attachment_guid, hash=gost_hash, provider_id=provider_id,
        )

    @classmethod
    def fetch(cls, file_id: ObjectId, provider_id: ObjectId) -> 'Attachment':
        """Получить данные вложения ГИС ЖКХ файла в Системе"""
        grid_file: GridOut = get_file_from_gridfs(file_id, raw=True)

        if hasattr(grid_file, 'uuid') and grid_file.uuid:  # не None?
            attachment_guid: UUID = as_guid(grid_file.uuid)  # hex -> UUID
        else:
            raise NoDataError("Идентификатор вложения не определен")

        uploader_id: ObjectId = getattr(grid_file, 'uploader', None)
        if not uploader_id:
            raise NoDataError("Принадлежность файла не определена")
        elif not provider_id:
            provider_id = uploader_id  # TODO без верификации?
        elif uploader_id != provider_id:
            raise NoDataError("Файл принадлежит другой организации")

        gis_store = FileStore(provider_id)  # контекст по умолчанию
        gis_store.inspect_file(attachment_guid)  # или download_file

        gost_hash: str = calc_old_hash(grid_file.read())  # хэш-сумма данных

        return cls(
            name=gis_store.file_name, description=gis_store.upload_context,
            guid=attachment_guid, hash=gost_hash, provider_id=provider_id,
        )

    def re_fetch(self):
        """
        Заново получить вложение ГИС ЖКХ из файлового хранилища ~ пере-залить

        При внесении изменений в ГИС ЖКХ требуются новые идентификаторы вложений
        """
        gis_store = FileStore(self.provider_id)  # контекст по умолчанию

        # перед скачиваем из репозитория ГИС ЖКХ загружаются сведения о файле
        file_data: bytes = gis_store.download_file(self.guid)

        # закачиваем файл обратно в репозиторий
        self.guid = gis_store.upload_file(self.name, file_data)  # : UUID

        return self  # пересчитывать хэш нет необходимости

    def _parse_meta(self, grid_file: GridOut):

        # https://www.mongodb.com/docs/manual/core/gridfs/

        self.name = grid_file.filename  # ~ name

        if hasattr(grid_file, 'uuid') and grid_file.uuid:
            self.guid = as_guid(grid_file.uuid)  # : str

        meta_data: dict = getattr(grid_file, 'metadata', {})  # WARN lazy

        self.description = meta_data.get('Description') \
            or grid_file.content_type  # WARN Deprecated
        self.hash = meta_data.get('AttachmentHASH') \
            or grid_file.md5  # WARN Deprecated
