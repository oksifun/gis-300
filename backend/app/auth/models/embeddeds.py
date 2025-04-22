# -*- coding: utf-8 -*-
from datetime import datetime

from mongoengine import (ObjectIdField, EmbeddedDocument,
                         EmbeddedDocumentField,
                         StringField, BooleanField, EmailField, DateTimeField,
                         EmbeddedDocumentListField, )

from app.area.models.area import ActorAreaEmbedded
from app.house.models.house import ActorHouseEmbedded
from processing.models.billing.embeddeds.phone import DenormalizedPhone
from processing.models.billing.provider.embeddeds import ActorProviderEmbedded


class SlugEmbedded(EmbeddedDocument):
    """Права на слаг."""
    
    slug = StringField()
    c = BooleanField()
    r = BooleanField()
    u = BooleanField()
    d = BooleanField()


class WorkerDepartmentEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    name = StringField()


class WorkerPositionEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    name = StringField()
    code = StringField(null=True)


class AccountEmbedded(EmbeddedDocument):
    """
    Акаунт-владелец пользователя
    """
    id = ObjectIdField(required=True, db_field='_id')
    owner_type = StringField(required=True)
    email = StringField(verbose_name="Пользовательский эл. адрес")
    number = StringField(
        required=True,
        regex=r'\d{0,13}',
        verbose_name="Номер ЛС",
    )
    str_name = StringField(verbose_name="Строка имени")
    last_name_upper = StringField(verbose_name="Строка имени")
    name = StringField(verbose_name="Наименование (поле юр.лица)")
    area = EmbeddedDocumentField(ActorAreaEmbedded)
    house = EmbeddedDocumentField(ActorHouseEmbedded)
    avatar = ObjectIdField(verbose_name="Пользовательское изображение")
    short_name = StringField()
    department = EmbeddedDocumentField(WorkerDepartmentEmbedded)
    position = EmbeddedDocumentField(WorkerPositionEmbedded)
    phones = EmbeddedDocumentListField(
        DenormalizedPhone,
        verbose_name="Список телефонов",
    )

    @classmethod
    def from_tenant(cls, tenant, business_types):
        return cls(
            id=tenant.id,
            owner_type='Tenant',
            email=tenant.email,
            number=tenant.number,
            str_name=tenant.str_name,
            last_name_upper=tenant.last_name_upper,
            area=ActorAreaEmbedded(
                id=tenant.area.id,
                str_number=tenant.area.str_number
            ),
            house=ActorHouseEmbedded(
                id=tenant.area.house.id,
                address=tenant.area.house.address,
                business_types=business_types,
            ),
            **(dict(name=tenant.name) if hasattr(tenant, 'name') else {})
        )

    @classmethod
    def from_worker(cls, worker):
        return cls(
            id=worker.id,
            owner_type='Worker',
            email=worker.email,
            number=worker.number,
            str_name=worker.str_name,
            short_name=worker.short_name,
            avatar=worker.avatar,
            department=WorkerDepartmentEmbedded(
                id=worker.department.id,
                name=worker.department.name,
            ),
            position=WorkerPositionEmbedded(
                id=worker.position.id,
                name=worker.position.name,
                code=worker.position.code,
            ),
            phones=worker.phones,
        )


class ConnectedActorEmbedded(EmbeddedDocument):
    """
    Ссылка на другого пользователя, принадлежащего тому же человеку
    """
    id = ObjectIdField(required=True, db_field='_id')
    owner = EmbeddedDocumentField(AccountEmbedded)
    provider = EmbeddedDocumentField(ActorProviderEmbedded)


class SlaveEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id', verbose_name='Ссылка на Actor')
    _type = StringField(
        verbose_name='Тип актера', choices=('RoboActor', 'Actor'))


class ChangedEmailEmbedded(EmbeddedDocument):
    new_email = EmailField(verbose_name='Новый email, на который хотим '
                                        'поменять')
    code = StringField(verbose_name='Код активации смены email')
    created = DateTimeField(
        verbose_name='Дата начала процесса смены email',
        default=datetime.now,
    )


class CloudMessagingEmbedded(EmbeddedDocument):
    fcm_token = StringField(required=True,
                            verbose_name='FCM-Token приложения '
                                         'в Firebase для отправки push-а')
    device_os = StringField(required=False,
                            verbose_name='Операционная система устройства')
