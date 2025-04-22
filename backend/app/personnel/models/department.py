from bson import ObjectId
from mongoengine import ValidationError
from mongoengine.base.fields import ObjectIdField
from mongoengine.document import EmbeddedDocument, Document
from mongoengine.fields import StringField, ListField, BooleanField, \
    EmbeddedDocumentField

from app.caching.models.denormalization import DenormalizationTask
from processing.models.billing.base import ProviderBinds, \
    BindedModelMixin
from app.personnel.models.denormalization.worker import SystemDepartmentEmbedded
from app.personnel.models.system_department import SystemDepartment
from processing.models.choices import SYSTEM_WORKERS_POSITIONS_CHOICES
from app.personnel.models.choices import SYSTEM_DEPARTMENTS_CHOICES
from processing.models.exceptions import CustomValidationError


class DepartmentEmbeddedPosition(EmbeddedDocument):
    id = ObjectIdField(db_field="_id", required=True, default=ObjectId)

    name = StringField(verbose_name='Наименование должности')
    code = StringField(
        null=True,
        choices=SYSTEM_WORKERS_POSITIONS_CHOICES,
        verbose_name='Код системной должности',
    )
    parent = ObjectIdField(
        null=True,
        verbose_name='Ссылка на родительскую должность'
    )
    system_position = ObjectIdField(
        verbose_name='Ссылка на системную должность',
    )
    inherit_parent_rights = BooleanField(
        required=True,
        default=False,
        verbose_name='Наследовать родительские права',
    )
    is_active = BooleanField(required=True, default=False)


class DepartmentSettingsEmbedded(EmbeddedDocument):
    tenant_tickets = BooleanField(default=False)
    request_control_visible = BooleanField(default=False)
    access_without_email = BooleanField(
        default=False,
        verbose_name='Доступ к системе без email-адреса',
    )


class Department(Document, BindedModelMixin):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Department',
    }

    name = StringField(
        required=True,
        min_length=1,
        verbose_name='Наименование отдела',
    )
    code = StringField(
        choices=SYSTEM_DEPARTMENTS_CHOICES,
        verbose_name='Код системного отдела',
    )
    parent = ObjectIdField(
        null=True,
        verbose_name='Ссылка на родительский отдел'
    )
    provider = ObjectIdField(
        required=True,
        verbose_name='Организация-владелец',
    )
    settings = EmbeddedDocumentField(
        DepartmentSettingsEmbedded,
        verbose_name='Настройки',
    )
    positions = ListField(
        EmbeddedDocumentField(DepartmentEmbeddedPosition),
        verbose_name='Должности',
    )
    system_department = EmbeddedDocumentField(
        SystemDepartmentEmbedded,
        verbose_name='Ссылка на системную должность',
    )
    inherit_parent_rights = BooleanField(
        required=True,
        default=False,
        verbose_name='Наследовать родительские права',
    )

    is_deleted = BooleanField()

    _binds = EmbeddedDocumentField(
        ProviderBinds,
        verbose_name='Привязки к организации'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._positions = [dict(x.to_mongo()) for x in self.positions]

    def save(self, *args,  **kwargs):
        self.restrict_changes()
        if not self._binds:
            self._binds = ProviderBinds(pr=self._get_providers_binds())
        self.denormalize()
        self.denormalize_position_codes()
        self.validate_positions_action()
        after_save = self._is_key_dirty('positions')
        if self._is_key_dirty('settings'):
            cabinet_denormalize_task = self._save_cabinet_denormalization_task()
        else:
            cabinet_denormalize_task = None
        result = super().save(*args,  **kwargs)
        self.update_workers(after_save)
        if cabinet_denormalize_task:
            from app.caching.tasks.denormalization import \
                sync_provider_permissions_to_cabinets
            sync_provider_permissions_to_cabinets.delay(
                self.provider,
                task_id=cabinet_denormalize_task.id,
            )
        return result

    def _save_cabinet_denormalization_task(self):
        task = DenormalizationTask(
            model_name='RoboActor',
            field_name='permissions',
            obj_id=self.provider,
            func_name='sync_provider_permissions_to_cabinets',
            kwargs={
                'provider_id': self.provider,
            },
        )
        task.save()
        return task

    def validate_positions_action(self):
        if len(self._positions) > len(self.positions):
            from app.personnel.models.personnel import Worker

            old_positions = {x['_id'] for x in self._positions}
            new_positions = {x.id for x in self.positions}
            deleted_positions = old_positions.difference(new_positions)
            if Worker.objects(position__id__in=list(deleted_positions)).count():
                raise CustomValidationError(
                    'Нельзя удалить должность, на которой числится сотрудник.'
                )

    def denormalize(self):
        system_positions = dict()
        if self.system_department and self.system_department.id:
            s_dep = SystemDepartment.objects(pk=self.system_department.id).get()
            self.system_department.code = s_dep.code
            if s_dep.positions:
                for pos in s_dep.positions:
                    system_positions[pos.id] = pos.code
        if self.positions:
            for item in self.positions:
                if item.system_position and not item.code and system_positions:
                    item.code = system_positions.get(item.system_position, None)

    def denormalize_position_codes(self):
        for position in self.positions:
            if position.system_position is not None:
                position.code = self._get_code_position(position.system_position)

    def _get_code_position(self, system_position):
        if system_position == None:
            return
        system_department = SystemDepartment.objects(
            positions__id=system_position
        ).first()
        for position in system_department.positions:
            if position.id == system_position:
                return position.code

    def update_workers(self, after_save):
        if not after_save:
            return

        from app.personnel.models.personnel import Worker

        for position in self.positions:
            if getattr(position, 'system_position', None):
                workers = Worker.objects(position__id=position.id,
                                         provider__id=self.provider,
                                         is_deleted__ne=True,
                                         is_dismiss__ne=True)
                for worker in workers._iter_results():
                    worker._mark_as_changed('position')
                    worker.save()

    def delete(self, *args, **kwargs):
        from app.personnel.models.personnel import Worker
        positions = {x['_id'] for x in self._positions}
        if Worker.objects(position__id__in=list(positions)).count():
            raise CustomValidationError(
                'Нельзя удалить отдел, в котором числятся сотрудники.'
            )
        super().delete(*args, **kwargs)
