from processing.data_producers.associated.base import get_spectator_department
from processing.data_producers.forms.file_base import FileOperations
from app.tickets.models.base import Spectator, Spectators, \
    DenormalizedAccount
from app.tickets.models.tenants import Ticket, TenantTicketMessage


def get_tenant_tickets(account, limit, offset):
    """
    Получение списка обращений жителя,
    отсортированных по дате создания обращений.
    """

    offset, limit = int(offset), int(limit)
    tickets = Ticket.objects(
        initial__author=account.id,
        is_deleted__ne=True,
        _type='TenantTicket',
    ).only(
        'id',
        'subject',
        'type',
        'status',
        'answer',
        'str_number',
        'initial',
        'incoming_date',
        'incoming_number',
    ).order_by(
        '-initial.created_at',
    ).as_pymongo()
    count = tickets.count()
    tickets = list(tickets[offset:limit + offset])
    for ticket in tickets:
        if not ticket.get('answer'):
            continue
        if not ticket['answer'].get('is_published'):
            ticket['answer'] = None
    return tickets, count


def create_ticket(body, ticket_type, tenant, provider_id,
                  department_id=None):
    """ Создание обращения в ЛКЖ """

    initial = dict(
        body=body,
        author=tenant.id,
        is_published=True,
    )
    if department_id:
        department = department_id
    else:
        department = get_spectator_department(provider_id)
    spectators = Spectators(
        Department=Spectator(allow=[department], deny=[]),
        Account=Spectator(allow=[], deny=[]),
        Position=Spectator(allow=[], deny=[]),
    )
    new_ticket = Ticket(
        type=ticket_type,
        initial=TenantTicketMessage(**initial),
        created_by=DenormalizedAccount(id=tenant.id, _type=tenant._type),
        spectators=spectators,
        subject=body[:40],
        _type=['TenantTicket'],
    )
    new_ticket.save(provider_id=provider_id)
    return new_ticket.id


def add_files_to_ticket(self, files, ticket_id, account_id):
    return FileOperations.add_files(
        model=Ticket,
        obj_id=ticket_id,
        files=files,
        account_id=account_id,
        file_field_path='initial.files',
        tenant_path='initial.author'
    )


def get_ticket_file(self, ticket_id, file_id, account_id):
    uuid = FileOperations.get_uuid_by_id(
        model=Ticket,
        file_id=file_id,
        account_id=account_id,
        obj_id=ticket_id,
        file_field_path='initial.files',
        tenant_path='initial.author'
    )
    if uuid:
        return uuid
    return FileOperations.get_uuid_by_id(
        model=Ticket,
        file_id=file_id,
        account_id=account_id,
        obj_id=ticket_id,
        file_field_path='answer.files',
        tenant_path='initial.author'
    )
