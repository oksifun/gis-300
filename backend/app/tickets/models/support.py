from mongoengine import EmbeddedDocument, StringField, BooleanField, Document, \
    EmbeddedDocumentField, DictField, Q, ValidationError, ObjectIdField, \
    ListField, EmbeddedDocumentListField, signals

from app.crm.models.crm import CRM, CRMEvent, CRMEventType, CRMDenormalized, \
    AccountDenormalized
from app.personnel.models.choices import SystemDepartmentCode
from app.personnel.models.denormalization.caller import AccountEmbeddedPosition
from app.personnel.models.department import Department
from app.personnel.models.personnel import Worker
from app.personnel.models.denormalization.worker import DepartmentEmbedded, \
    WorkerDenormalized, WorkerPositionDenormalized
from app.tickets.models.base import BasicTicket, Spectator, Spectators, \
    TicketMessageMixin
from processing.models.billing.account import Account, Tenant
from processing.models.billing.base import BindedModelMixin, \
    ProviderAccountBinds
from processing.models.billing.provider.main import Provider
from processing.models.choices import TicketAccessLevelCode, \
    SUPPORT_TICKET_STATUS_CHOICES, SupportTicketStatus
from settings import ZAO_OTDEL_PROVIDER_OBJECT_ID


class RedmineTask(EmbeddedDocument):
    url = StringField(null=True)
    has_url = BooleanField(required=True, default=False)
    is_completed = BooleanField(required=True, default=False)


class TicketProviderEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    str_name = StringField()


class TicketOwnerEmbedded(EmbeddedDocument):
    provider = EmbeddedDocumentField(TicketProviderEmbedded)
    managers = ListField(
        ObjectIdField(),
        verbose_name='Кто работает с организацией автора тикета',
    )


class DepartmentProviderEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")


class TicketCreatorEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    department = EmbeddedDocumentField(DepartmentProviderEmbedded)
    _type = ListField(StringField())


class TicketAuthorEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    str_name = StringField()
    department = EmbeddedDocumentField(DepartmentEmbedded)
    position = EmbeddedDocumentField(AccountEmbeddedPosition)
    _type = ListField(StringField())


class SupportTicketMessage(EmbeddedDocument, TicketMessageMixin):
    pass


class SupportTicket(BasicTicket, BindedModelMixin, Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'SupportTicket',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'type',
            'status',
            '-initial.created_at',
            {
                'fields': [
                    'executor.id',
                    '-initial.created_at',
                ],
            },
            {
                'fields': [
                    '_binds.ac',
                    '-initial.created_at',
                ],
            },
            {
                'fields': [
                    '_binds.pr',
                    '-initial.created_at',
                ],
            },
            {
                'fields': [
                    'owner.provider.id',
                    '-initial.created_at',
                ],
            },
        ]
    }

    status = StringField(
        required=True,
        choices=SUPPORT_TICKET_STATUS_CHOICES,
        default=SupportTicketStatus.NEW,
        verbose_name='Статус тикета',
    )
    created_by = EmbeddedDocumentField(
        TicketCreatorEmbedded,
        required=True,
        verbose_name='Пользователь-создатель тикета',
    )
    owner = EmbeddedDocumentField(
        TicketOwnerEmbedded,
        verbose_name='Провайдер автора тикета',
    )
    author = EmbeddedDocumentField(
        TicketAuthorEmbedded,
        verbose_name='Автор тикета'
    )
    initial = EmbeddedDocumentField(
        SupportTicketMessage,
        required=True,
        verbose_name='Стартовое сообщение',
    )
    comments = EmbeddedDocumentListField(
        SupportTicketMessage,
        verbose_name='Комментарии',
    )
    redmine = EmbeddedDocumentField(RedmineTask, default=RedmineTask)
    metadata = DictField()
    _binds = EmbeddedDocumentField(
        ProviderAccountBinds,
    )
    mobile_app = BooleanField(default=False)

    @classmethod
    def create_crm_event(cls, pk):
        instance = cls.objects(pk=pk).as_pymongo().get()
        account = cls._get_account(instance)
        if not account.get('provider'):
            return
        provider = Provider.objects(
            id=account['provider']['_id'],
        ).first()
        crm = CRM.objects(
            owner=ZAO_OTDEL_PROVIDER_OBJECT_ID,
            provider__id=provider.id,
        ).first()
        if not crm:
            return
        ticket = dict(
            id=instance['_id'],
            initial=instance['initial'],
            str_number=instance['str_number'],
            author=instance['author'],
            subject=instance['subject'],
            type=instance['type'],
            _type=instance['_type'],
            status=instance['status'],
        )
        event = CRMEvent.objects.filter(
            ticket__id=instance['_id']).first()
        if event:
            first_comment = (instance['comments'][0]['created_at']
                             if instance.get('comments') else None)
            event.update(status=crm.status)
            event.update(ticket=ticket)
            event.update(created=first_comment)
            event.save()
            return
        event = CRMEvent(
            crm=CRMDenormalized(id=crm.id),
            account=AccountDenormalized(id=account['_id']),
            status=crm.status,
            _type=[CRMEventType.SUPPORT_TICKET],
            ticket=ticket,
            created=None,
            date=instance['initial']['created_at'],

        )
        event.save()

    @staticmethod
    def _get_account(ticket_instance_as_dict):
        if 'Tenant' in ticket_instance_as_dict['_type']:
            account = Tenant.objects(
                pk=ticket_instance_as_dict['initial']['author'],
            ).only(
                'short_name',
                'str_name',
                '_type',
            ).as_pymongo()
        else:
            account = Worker.objects(
                pk=ticket_instance_as_dict['initial']['author'],
            ).only(
                'short_name',
                'str_name',
                'department',
                '_type',
                'provider',
                'position',
            ).as_pymongo()
        return account.first()

    def save(self, *args, **kwargs):
        if self.pk:
            self.handle_statuses()
        if self._is_triggers(['executor']):
            self.denormalize_own_executor()
        self.denormalize_author_and_provider()
        self.get_created_by()
        self.get_binds()
        self.generate_number()
        self.denormalize_spectators()
        return super().save(*args, **kwargs)

    @classmethod
    def post_save(cls, sender, document, **kwargs):
        cls.create_crm_event(document.id)

    def denormalize_own_executor(self):
        if not getattr(self.executor, 'id', False):
            self.executor = None
            return

        executor_fields = ['id', 'short_name',
                           'department', 'position',
                           '_type']
        worker = Worker.objects(
            pk=self.executor.id
        ).as_pymongo(
        ).only(
            *executor_fields
        ).first()

        executor_position = WorkerPositionDenormalized(
            id=worker['position']['_id'],
            name=worker['position']['name'],
            code=worker['position']['code']
        )

        executor = WorkerDenormalized(
            id=worker['_id'],
            short_name=worker['short_name'],
            department=worker['department'],
            position=executor_position,
            _type=worker['_type']
        )
        self.executor = executor

    def handle_statuses(self):
        ticket = SupportTicket.objects(id=self.pk).first()

        if ticket.status in [
            SupportTicketStatus.NEW,
            SupportTicketStatus.AWAITING
        ] and self.status == SupportTicketStatus.CLOSED:
            raise ValidationError('Нельзя закрыть сообщение без ответа.')

        if ticket.status == SupportTicketStatus.CLOSED \
                and (self._is_key_dirty('comments')
                     or self._is_key_dirty('initial')):
            raise ValidationError('Закрыто для редактирования.')

        author_ticket = ticket.initial.author
        if 'comments' in self._changed_fields and \
                any([c.author != author_ticket for c in self.comments]):
            if author_ticket == self.comments[-1]['author']:
                self.status = SupportTicketStatus.AWAITING
            else:
                self.status = SupportTicketStatus.PERFORMED

    @staticmethod
    def filter_comments(comments, request, ignore_filter=False):
        if ignore_filter:
            return comments
        data = []
        user = request.user.id
        comments = sorted(comments, key=lambda k: k['created_at'], reverse=True)
        for c in comments:
            if c['author'] != user and not c['is_published']:
                continue
            data.append(c)
        return data

    def denormalize_author_and_provider(self):
        account = Account.objects(
            pk=self.initial.author,
        ).only(
            'str_name', 'department', '_type', 'provider', 'position'
        ).as_pymongo().first()

        author_query = dict(
            id=self.initial.author,
            str_name=account['str_name'],
            _type=account['_type']
        )
        if account.get('department'):
            department = DepartmentEmbedded(
                id=account['department']['_id'],
                name=account['department']['name'],
                provider=account['provider']['_id'],
                system_department=account['department'].get('system_department')
            )
            author_query.update(dict(department=department))
        if account.get('position'):
            position = AccountEmbeddedPosition(
                id=account['position'].get('_id'),
                name=account['position'].get('name'),
                code=account['position'].get('code')
            )
            author_query.update(dict(position=position))
        self.author = TicketAuthorEmbedded(**author_query)

        if account.get('provider'):
            provider = Provider.objects(
                id=account['provider']['_id']
            ).first()
            self.owner = TicketOwnerEmbedded(
                provider=TicketProviderEmbedded(
                    id=account['provider']['_id'],
                    str_name=provider.str_name
                ),
                managers=provider.managers
            )

    def get_created_by(self):
        account = Account.objects(
            id=self.created_by.id
        ).only('department', '_type', 'provider').as_pymongo().first()

        if account.get('department'):
            department, _type = account['department'], account['_type']
            self.created_by = TicketCreatorEmbedded(
                id=self.created_by.id,
                department=DepartmentProviderEmbedded(
                    id=department['_id'],
                ),
                _type=_type,
            )
        else:
            _type = account['_type']
            self.created_by = TicketCreatorEmbedded(
                id=self.created_by.id,
                _type=_type,
            )

    def get_binds(self):
        """ Собираем привязки со всех, кто имеет доступ """
        pr = [ZAO_OTDEL_PROVIDER_OBJECT_ID]
        ac = set()
        if self.author.department:
            pr.append(self.owner.provider.id)
            accounts = Worker.objects(
                Q(
                    _type='Worker',
                    provider__id=self.owner.provider.id
                )
                & (
                        Q(settings__tickets_access_level='all')
                        | (
                            Q(department__id=self.author.department.id)
                            & Q(settings__tickets_access_level='by_dept')
                        )
                )
            )
            ac = set(x['id'] for x in accounts)
        ac.add(self.author.id)
        self._binds = ProviderAccountBinds(pr=pr, ac=ac)

    def generate_number(self):
        if self._created or 'number' in self._changed_fields:
            self._generate_number(provider_id=self.owner.provider.id)

    def denormalize_spectators(self):
        if hasattr(self.created_by, 'department'):
            departments = Department.objects(
                provider=self.owner.provider.id,
                code=SystemDepartmentCode.SUPPORT,
            ).only('id')
            departments_ids = [x['id'] for x in departments]
            self.spectators = Spectators(
                Department=Spectator(allow=departments_ids, deny=[]),
                Account=Spectator(allow=[], deny=[]),
                Position=Spectator(allow=[], deny=[]),
            )

    @classmethod
    def process_provider_binds(cls, provider_id, **kwargs):
        pulled = cls.objects(
            _type='SupportTicket',
            owner__provider__id__ne=provider_id,
            _binds__pr=provider_id,
        ).update(
            pull___binds__pr=provider_id,
        )
        pushed = cls.objects(
            _type='SupportTicket',
            owner__provider__id=provider_id,
            _binds__pr__ne=provider_id,
        ).update(
            add_to_set___binds__pr=provider_id,
        )
        return pushed, pulled

    @classmethod
    def process_account_binds(cls, account_id, **kwargs):
        worker = Worker.objects(
            pk=account_id,
        ).only(
            'department.id',
            'department.provider',
            'settings.tickets_access_level'
        ).first()
        provider_id = worker.department.provider
        department_id = worker.department.id
        tickets_access_level = worker.settings.tickets_access_level
        to_pull = dict(_binds__ac=account_id)
        to_push = dict(_binds__ac__ne=account_id)
        if tickets_access_level == TicketAccessLevelCode.ALL:
            to_pull['owner__provider__id__ne'] = provider_id
            to_push['owner__provider__id'] = provider_id
        elif tickets_access_level == TicketAccessLevelCode.BY_DEPT:
            to_pull['author__department__id__ne'] = department_id
            to_push['author__department__id'] = department_id
        else:
            to_pull['author__id__ne'] = account_id
            to_push['author__id'] = account_id
        pulled = cls.objects(
            Q(**to_pull),
            _type='SupportTicket',
        ).update(pull___binds__ac=account_id)
        pushed = cls.objects(
            Q(**to_push),
            _type='SupportTicket',
        ).update(add_to_set___binds__ac=account_id)
        return pushed, pulled


signals.post_save.connect(SupportTicket.post_save, sender=SupportTicket)
