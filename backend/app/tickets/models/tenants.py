from mongoengine import Document, EmbeddedDocumentField, StringField, \
    BooleanField, EmbeddedDocumentListField, EmbeddedDocument

from app.area.models.area import Area
from app.tickets.models.base import BasicTicket, TicketMessageMixin
from app.messages.tasks.users_tasks import \
    update_users_tickets
from processing.models.billing.account import Tenant, Account
from processing.models.billing.embeddeds.area import \
    DenormalizedAreaShortWithFias
from processing.models.choices import TicketStatus


class TenantTicketMessage(EmbeddedDocument, TicketMessageMixin):
    str_name = StringField()
    is_read = BooleanField(default=False)


class Ticket(BasicTicket, Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Ticket',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'initial.author',
            'area.id',
            'initial.created_at',
            'executor.id',
            {
                'fields': [
                    'initial.author',
                    '-initial.created_at',
                ],
            },
            {
                'fields': [
                    'created_by.id',
                    '-initial.created_at',
                ],
            },
            {
                'fields': [
                    'executor.id',
                    '-initial.created_at',
                ],
            },
            {
                'fields': [
                    'spectators.Account.allow',
                    '-initial.created_at',
                ],
            },
            {
                'fields': [
                    'spectators.Department.allow',
                    '-initial.created_at',
                ],
            },
            {
                'fields': [
                    'spectators.Position.allow',
                    '-initial.created_at',
                ],
            },
            {
                'fields': [
                    'executor.department.provider',
                    '-initial.created_at',
                ],
            },
            {
                'fields': [
                    'created_by.department.provider',
                    '-initial.created_at',
                ],
            },
        ],
    }

    area = EmbeddedDocumentField(DenormalizedAreaShortWithFias)
    answer = EmbeddedDocumentField(
        TenantTicketMessage,
        verbose_name='Ответы автору тикета в хронологическом порядке',
    )
    initial = EmbeddedDocumentField(
        TenantTicketMessage,
        required=True,
        verbose_name='Стартовое сообщение',
    )
    comments = EmbeddedDocumentListField(
        TenantTicketMessage,
        verbose_name='История сообщений',
    )

    def patch_status(self):
        """
        Формируем статус тикета на основании входящих данных
        """
        if self.status == TicketStatus.NEW and self.executor:
            # Обработка действия «Принять к исполнению»
            self.status = TicketStatus.ACCEPTED
        elif (
                self.status == TicketStatus.ACCEPTED
                and self.answer
                and self.answer.is_published is True
        ):
            # Обработка действия «Закрыть с ответом»
            self.status = TicketStatus.CLOSED
        return self

    def save(self, *args, **kwargs):
        if 'Tenant' in self.created_by._type:
            self.denormalize_area()
        self.generate_number(**kwargs)
        self.patch_status()
        super().save(*args, **kwargs)
        self.update_users_tasks()
        self.check_empty_executor()

    def check_empty_executor(self):
        ticket = \
            Ticket.objects(pk=self.pk).only('executor').as_pymongo().first()
        if ticket and ticket.get('executor'):
            if not ticket['executor'].get('_type'):
                Ticket.objects(
                    pk=self.pk,
                ).update(
                    __raw__={
                        '$unset': {
                            'executor': 1,
                        },
                    },
                )

    def denormalize_area(self):
        tenant = Tenant.objects(pk=self.created_by.id).get()
        area = Area.objects(pk=tenant.area.id).get()
        self.area = DenormalizedAreaShortWithFias.from_ref(area)

    def update_users_tasks(self):
        """ 'Уведомление' о новой заявке"""
        update_condition = any((
            self._created,
            'executor' in self._changed_fields,
            'spectators' in self._changed_fields
        ))
        if update_condition:
            workers = list()
            if self.executor:
                workers.append(self.executor.id)
            if self.spectators:
                workers.extend(self.spectators.Account.allow)
            update_users_tickets.delay(workers)

    def generate_number(self, **kwargs):
        """ Генерация номера заявки """
        if self._created or 'number' in self._changed_fields:
            provider_id = (
                kwargs['provider_id']
                if kwargs.get('provider_id')
                else self._get_provider()
            )
            self._generate_number(provider_id)

    def _get_provider(self):
        dept_exists_condition = (
                self.spectators
                and self.spectators.Department
                and self.spectators.Department.allow
        )
        if dept_exists_condition:
            from app.personnel.models.department import Department as Dp
            dp_id = self.spectators.Department.allow[0]
            dept = Dp.objects(id=dp_id).only('provider').as_pymongo().get()
            return dept['provider']

        return self._get_provider_id_by_account()

    def _get_provider_id_by_account(self):
        from app.house.models.house import House
        account = Account.objects(id=self.created_by.id).as_pymongo().get()
        house_id = account['area']['house']['_id']
        house = House.objects(pk=house_id).get()
        provider = house.get_provider_by_business_type('udo')
        if not provider:
            raise PermissionError('Не нашлась организация!')
        return provider
