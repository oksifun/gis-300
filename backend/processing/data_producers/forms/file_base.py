from lib.gridfs import put_file_to_gridfs
from processing.models.billing.files import Files
from app.requests.models.request import PhotoEmbedded
from app.tickets.models.tenants import Ticket


class FileOperations:

    @classmethod
    def add_files(
            cls, model, obj_id, files, account_id, file_field_path, tenant_path
    ):
        """ Универсальный метод для загрузки файлов через ЛКЖ """

        obj_model = model.objects(id=obj_id).get()
        tenant_id = cls._get_attr_by_path(tenant_path.split('.'), obj_model)
        if tenant_id != account_id:
            raise PermissionError('Недостаточно прав!')
        files_blueprint = []
        # Кладём файлы в базу
        for _, file in files.items():
            file_id, uuid = put_file_to_gridfs(
                model.__name__,
                obj_id,
                file.read(),
                filename=file.name,
                content_type=file.content_type
            )
            files_blueprint.append(dict(
                id=file_id,
                file=file_id,
                uuid=uuid,
                filename=file.name,
                name=file.name,
            ))
        if model.__name__ == 'Ticket':
            new_files = [Files(**f) for f in files_blueprint]
        else:
            # Модель Request
            new_files = [
                PhotoEmbedded(file=Files(**f)) for f in files_blueprint
            ]
        model_file_field = cls._get_attr_by_path(
            path=file_field_path.split('.'),
            obj_model=obj_model
        )
        if model_file_field:
            model_file_field.extend(new_files)
        else:
            cls._set_attr_by_path(
                path=file_field_path.split('.'),
                obj_model=obj_model,
                new_attr=new_files
            )
        obj_model.save()
        return obj_model.id

    @classmethod
    def _get_attr_by_path(cls, path, obj_model):
        attr = None
        for field in path:
            attr = getattr(attr if attr else obj_model, field, None)
        return attr

    @classmethod
    def _set_attr_by_path(cls, path, obj_model, new_attr):
        if len(path) > 1:
            attr = cls._get_attr_by_path(path[:-1], obj_model)
            setattr(attr, path[-1], new_attr)
        else:
            setattr(obj_model, path[-1], new_attr)

    @classmethod
    def get_uuid_by_id(cls, model, file_id, obj_id,
                       account_id, file_field_path, tenant_path):
        obj_model = model.objects(id=obj_id).get()
        tenant_id = cls._get_attr_by_path(tenant_path.split('.'), obj_model)
        if tenant_id != account_id:
            raise PermissionError('Недостаточно прав!')

        model_file_field = cls._get_attr_by_path(
            path=file_field_path.split('.'),
            obj_model=obj_model
        )
        for f in model_file_field:
            if isinstance(obj_model, Ticket):
                if f.id == file_id:
                    return f.uuid
            else:
                if f.file.file == file_id:
                    return f.file.uuid
