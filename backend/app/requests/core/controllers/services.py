import datetime as dt
from typing import (
    Iterable,
    Union,
)

from app.messages.core.email.extended_mail import TicketMail
from app.personnel.models.personnel import Worker
from app.requests.core.controllers.selectors import RequestSelector
from app.requests.models.embedded_docs import (
    ControlMessageEmbedded,
    EmbeddedMonitoring,
    PersonInChargeEmbedded,
)
from app.requests.models.request import Request

from bson import ObjectId

from jinja2 import (
    Environment,
    FileSystemLoader,
)

from processing.models.billing.account import Tenant
from processing.models.billing.base import BindsPermissions
from processing.models.billing.provider.main import Provider

from rest_framework import exceptions


class RequestService:

    def __init__(
            self,
            request: Request = None,
            binds: Union[BindsPermissions, dict] = None,
            pk: ObjectId = None,
    ):
        if request:
            self.request = request
        elif pk:
            self.request = RequestSelector.get_object(
                pk=pk,
                binds=binds if binds else {},
            )
        else:
            raise Exception('Невозможно создать экземпляр класса')

    def add_monitoring_message(
            self,
            created_by: ObjectId,
            message: str,
            save: bool = False,
    ) -> Request:
        """
        Добавление сообщения контролирующим лицом

        Args:
            created_by: кем создано сообщение
            message: текст сообщения
            save: сохранять ли объект в бд

        Returns:
            Объект заявки
        """
        self._check_monitoring_message_fields()
        self.request.monitoring.messages.append(
            ControlMessageEmbedded(
                created_by=created_by,
                message=message,
            )
        )
        if save:
            self.request.save()
        return self.request

    def add_persons_in_charge(
            self,
            persons: Iterable[ObjectId],
            save: bool = False,
    ) -> Request:
        """
        Добавление ответственных за заявку лиц контролирующим лицом

        Args:
            persons: итерируемый объект
            save: сохранять ли объект в бд

        Returns:
            Объект заявки
        """
        self._check_monitoring_pic_fields()
        new_persons = self._filter_inactive_and_already_set_pic(persons)
        self.request.monitoring.persons_in_charge.extend(
            [
                PersonInChargeEmbedded(id=_id)
                for _id in new_persons
            ]
        )
        if save:
            self.request.save(skip_notification=True)
        return self.request

    def _filter_inactive_and_already_set_pic(
            self,
            persons: Iterable[ObjectId],
    ) -> Iterable:
        active_workers = Worker.active_workers(
            provider__id=self.request.provider.id
        ).values_list('id')
        set_persons_in_charge = set(
            e.id for e in self.request.monitoring.persons_in_charge
        )
        new_persons = set(persons) - set_persons_in_charge
        return new_persons & set(active_workers)

    def del_persons_in_charge(
            self,
            persons: Iterable[ObjectId],
            save: bool = False,
    ) -> Request:
        """
        Удаление ответственных за заявку лиц контролирующим лицом

        Args:
            persons: итерируемый объект
            save: сохранять ли объект в бд

        Returns:
            Объект заявки
        """
        if not save:
            self.request.monitoring.persons_in_charge = [
                e for e in self.request.monitoring.persons_in_charge
                if e.id not in persons
            ]
        else:
            self.request.update(
                pull__monitoring__persons_in_charge__id__in=persons
            )
        return self.request

    def review_monitoring(
            self,
            person_id: ObjectId,
            save: bool = False,
    ) -> Request:
        """
        "Ознакомление с контролем заявки" ответственным лицом -
        проставление в informed объекта person_in_charge текущей даты

        Args:
            person_id: ObjectId ответственного лица
            save: сохранять ли объект в бд

        Returns:
            Объект заявки
        """
        self._check_monitoring_pic_fields()
        informed = False
        for person in self.request.monitoring.persons_in_charge:
            if person.id == person_id:
                person.informed = dt.datetime.now()
                informed = True
                break
        if not informed:
            raise exceptions.ValidationError(
                detail='Пользователя нет в ответственных лицах заявки',
            )
        if save:
            self.request.save()
        return self.request

    def _check_embedded_monitoring_existence(self):
        if not self.request.monitoring:
            self.request.monitoring = EmbeddedMonitoring()

    def _check_embedded_monitoring_messages_existence(self):
        if not self.request.monitoring.messages:
            self.request.monitoring.messages = []

    def _check_embedded_monitoring_persons_existence(self):
        if not self.request.monitoring.persons_in_charge:
            self.request.monitoring.persons_in_charge = []

    def _check_monitoring_message_fields(self):
        self._check_embedded_monitoring_existence()
        self._check_embedded_monitoring_messages_existence()

    def _check_monitoring_pic_fields(self):
        self._check_embedded_monitoring_existence()
        self._check_embedded_monitoring_persons_existence()


class RequestMailService:
    def __init__(self, request):
        self.request = request

    def request_monitoring_message_notify(self):
        persons_ids = self.request.persons_in_charge_ids
        provider = Provider.objects(id=self.request.provider.id).get()
        request_url = (
            f'{provider.get_url()}/#/requests/detail/{self.request.id}'
        )
        persons = Worker.objects(id__in=persons_ids).all()

        if self.request.dispatcher and self.request.dispatcher.id:
            dispatcher = Worker.objects(pk=self.request.dispatcher.id).first()
        else:
            dispatcher = None

        if self.request.tenant and self.request.tenant.id:
            tenant = Tenant.objects(pk=self.request.tenant.id).first()
        else:
            tenant = None
        if not tenant:
            tenant = dispatcher
        theme = f'Сотрудником, контролирующим заявку №{self.request.number},' \
                f' добавлено новое сообщение'

        for person in persons:
            if person.email:
                body = self._get_body_context(
                    self.request.provider,
                    worker=person,
                    tenant=tenant,
                    dispatcher=dispatcher,
                    theme=theme,
                    url=request_url,
                )
                mail = TicketMail(
                    addresses=person.email,
                    subject=theme,
                    body=body,
                    provider_id=self.request.provider.id,
                )
                mail.send()

    def _get_body_context(self, provider, worker, tenant, dispatcher, theme,
                          url):
        """Генерация тела письма на основе шаблона"""
        context = dict(
            provider=provider,
            request=self.request,
            account=worker,
            tenant=tenant,
            dispatcher=dispatcher,
            title=theme,
            url=url,
        )
        return self.get_request_mail_template().render(context)

    @staticmethod
    def get_request_mail_template():
        """
        Загрузка шаблона для письма, информируеющего работников об изменении
        исполнителя заявки.
        """
        template_name = 'requests.html'
        template_path = './templates/jinja/mail'
        # Загрузка окружения для их наследования
        env = Environment(loader=FileSystemLoader(template_path))
        template = env.get_template(template_name)
        return template
