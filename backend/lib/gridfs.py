from mimetypes import guess_type
from uuid import uuid4

from gridfs import GridFS
from mongoengine import DoesNotExist
from pymongo import MongoClient

import settings


def put_file_to_gridfs(resource_name, resource_id, file_bytes, uuid=None,
                       filename=None, uploader=None, **kwargs):
    if uuid is None:
        file_uuid = uuid4().hex
    else:
        file_uuid = uuid

    client = MongoClient(
        host=settings.DATABASES['files']['host'],
        connectTimeoutMS=20,
    )
    database = getattr(client, settings.DATABASES['files']['db'])

    if not kwargs.get('content_type'):
        mime_type = 'text/plain'
        if filename:
            mime_type, _ = guess_type(filename)
        kwargs['content_type'] = mime_type

    file_id = GridFS(database=database).put(
        file_bytes,
        uuid=file_uuid,
        owner_resource=resource_name,
        owner_id=resource_id,
        uploader=uploader,
        filename=filename,
        **kwargs
    )
    if uuid:
        return file_id
    else:
        return file_id, file_uuid


def get_file_from_gridfs(file_id, uuid=None, raw=False,
                         permissions_filter=None):
    """
    Достаёт файл из гридфс по ИД или по uuid. Чтобы найти по uuid, надо
    передать file_id=None. Параметр raw=True отдаст объект GridFS. Иначе
    вернутся имя файла и байты
    """
    client = MongoClient(
        host=settings.DATABASES['files']['host'],
        connectTimeoutMS=20,
    )
    database = getattr(client, settings.DATABASES['files']['db'])
    query = {'_id': file_id} if file_id else {'uuid': uuid}
    if permissions_filter:
        query.update(permissions_filter)
    file = GridFS(database=database).find_one(query)
    if not file:
        raise DoesNotExist()
    if raw:
        return file
    file_bytes = file.read()
    return file.filename, file_bytes


def delete_file_in_gridfs(file_id, uuid=None, permissions_filter=None):
    """
    Удаляет файл вз гридфс по ИД или по uuid. Чтобы найти по uuid, надо
    передать file_id=None
    """
    client = MongoClient(
        host=settings.DATABASES['files']['host'],
        connectTimeoutMS=20,
    )
    database = getattr(client, settings.DATABASES['files']['db'])
    query = {'_id': file_id} if file_id else {'uuid': uuid}
    if permissions_filter:
        query.update(permissions_filter)
    file = GridFS(database=database).find_one(query)
    if not file:
        raise DoesNotExist()
    GridFS(database=database).delete(file._id)

