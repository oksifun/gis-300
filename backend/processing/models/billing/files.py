from bson import ObjectId
from mongoengine import (
    EmbeddedDocument,
    IntField,
    ObjectIdField,
    StringField,
)

from lib.gridfs import get_file_from_gridfs, put_file_to_gridfs


class FileOperationError(Exception):
    pass


class Files(EmbeddedDocument):
    """ Регламентированное поле для хранения файлов """

    file = ObjectIdField(null=True)
    name = StringField(null=True)
    size = IntField(null=True)

    # TODO Удалить после миграции и перехода заявок на v4
    id = ObjectIdField(db_field='_id', null=True)
    filename = StringField(null=True)
    uuid = StringField(null=True)

    def load_file(self):
        if not self.file and not self.uuid:
            raise FileOperationError('Не указан file и uuid')
        query = (
            dict(file_id=self.file)
            if self.file
            else dict(file_id=None, uuid=self.uuid)
        )
        return get_file_from_gridfs(**query)

    def save_file(self, body: bytes, name: str, owner_id: ObjectId = None):
        # кладём файл в базу
        file_id, uuid = put_file_to_gridfs(
            resource_name=None,
            resource_id=owner_id if owner_id else None,
            file_bytes=body,
            filename=name
        )
        self.file = file_id
        self.name = name
