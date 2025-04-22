# -*- coding: utf-8 -*-
from mongoengine import (
    EmbeddedDocument,
    ObjectIdField,
    StringField,
    EmbeddedDocumentField,
    BooleanField,
)

from app.personnel.models.denormalization.worker import SystemDepartmentEmbedded


class NameWithIdEmbedded(EmbeddedDocument):
    """Общий embedded document содержащий какое-то имя и какой-то id."""
    id = ObjectIdField(db_field="_id")
    name = StringField()


class AccountEmbeddedDepartment(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    system_department = EmbeddedDocumentField(SystemDepartmentEmbedded)
    name = StringField()
    provider = ObjectIdField()


class AccountEmbeddedPosition(EmbeddedDocument):
    # копия DepartmentEmbeddedPosition
    id = ObjectIdField(db_field="_id")

    name = StringField()  # String,
    # Any(SystemDepartment.SystemPosition.ChiefPosition,
    # SystemDepartment.SystemPosition.AccountantPosition),
    code = StringField(null=True)  # TODO choices
    parent = ObjectIdField(null=True)  # Model.Id,  # Ссылка на родительскую должность

    # SystemDepartment.SystemPosition.Id,
    system_position = ObjectIdField(null=True)  # Ссылка на системную должность

    # Required(Boolean, default=False),  # наследовать родительские права
    inherit_parent_rights = BooleanField(default=False)

    # Required(Boolean, default=False),
    is_active = BooleanField(default=False)


class ProviderEmbedded(EmbeddedDocument):
    """Embedded document для провайдера работника в звонках."""
    id = ObjectIdField(db_field="_id")
    str_name = StringField(verbose_name="Название компании")


class WorkerCallEmbedded(EmbeddedDocument):
    """Embedded document для звонившего/отвечающего работника."""
    id = ObjectIdField(db_field="_id")
    name = StringField(verbose_name="ФИО работника")
    position = EmbeddedDocumentField(AccountEmbeddedPosition)
    department = EmbeddedDocumentField(AccountEmbeddedDepartment)
    phone_number = StringField(
        verbose_name="Номер телефона",
    )
    provider = EmbeddedDocumentField(ProviderEmbedded)

    @property
    def get_provider_id(self):
        return str(self.provider._id)
    

class ShortWorkerEmbedded(EmbeddedDocument):
    """Embedded document для работника и организации."""
    id = ObjectIdField(db_field="_id")
    name = StringField(verbose_name="ФИО работника")
    provider = EmbeddedDocumentField(ProviderEmbedded)
    email = StringField(verbose_name="Email сотрудника")
    phone = StringField(verbose_name="Номер телефона")

    @property
    def get_provider_id(self):
        return str(self.provider._id)


class WorkerInCourtCaseEmbedded(EmbeddedDocument):
    """Embedded document для сотрудника с отделом."""
    id = ObjectIdField(db_field="_id", required=True)
    name = StringField(verbose_name="ФИО работника")
    position = EmbeddedDocumentField(NameWithIdEmbedded)
    department = EmbeddedDocumentField(NameWithIdEmbedded)
    phone_number = StringField(verbose_name="Номер телефона", required=False,
                               null=True)
    provider = EmbeddedDocumentField(ProviderEmbedded)
