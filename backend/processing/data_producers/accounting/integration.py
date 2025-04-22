from bson import ObjectId
from mongoengine import DoesNotExist

from lib.gridfs import delete_file_in_gridfs
from lib.helpfull_tools import DateHelpFulls
from processing.celery.tasks.swamp_thing.accounting_exchange import \
    get_reconciliation_archive, \
    get_bill_and_invoice_archive, PROVIDER_DAYS_TO_DEBTOR
from processing.models.billing.account import Account
from processing.models.billing.provider.main import Provider
from processing.models.billing.own_contract import OwnContract, \
    ArchiveDocuments, DocumentStackEmbedded
from processing.models.tasks.accounting_sync import OwnIssuedDocuments, \
    OwnSentNomenclatures


def _get_field_value(contract: dict, obj: str, field: str):
    return (
        str(contract['doc_stack'].get(obj, {}).get(field, 'null'))
        if contract.get('doc_stack')
        else 'null'
    )


def get_contract_balances(user: Account, provider: Provider):
    """Получение сальдо по контрактам для управленцев системных позиций"""

    # Если пользователь супер, то ему можно увидеть ЭТО
    if not user.is_super:
        # Проверка того, что пользователь имеет системный код
        position_code = user.position.code
        sys_positions = 'acc1', 'ch1', 'ch2', 'ch3'
        if not (position_code and position_code in sys_positions):
            return []

    fields = 'id', 'date', 'number', 'balance', 'doc_stack'
    contracts = tuple(
        OwnContract.objects(client=provider.pk).only(*fields).as_pymongo()
    )
    result = [
        dict(
            id=str(contract['_id']),
            date=contract['date'],
            number=contract['number'],
            balance=contract['balance']['value'],
            balance_date=contract['balance']['updated'],
            debtor_date=contract['balance'].get('debtor_date'),
            disable_when_debtor=provider.disable_when_debtor,
            provider_days_to_debtor=PROVIDER_DAYS_TO_DEBTOR,
            # Состояние готовности акта сверки к скачке
            reconciliation_act=dict(
                state=_get_field_value(contract, 'act', 'state'),
                uuid=_get_field_value(contract, 'act', 'uuid'),
                description=_get_field_value(contract, 'act', 'description'),
                updated=_get_field_value(contract, 'act', 'updated')
            ),
            archive_documents=dict(
                state=_get_field_value(contract, 'bill', 'state'),
                uuid=_get_field_value(contract, 'bill', 'uuid'),
                description=_get_field_value(contract, 'bill', 'description'),
                updated=_get_field_value(contract, 'bill', 'updated')
            )
        )
        for contract in contracts
        if contract.get('balance')
    ]
    return result


def get_document_stack_archive(
        provider: Provider,
        contract: ObjectId,
        date_from,
        date_till,
        archive_type: str,
        account=None,
        url=None,
):
    contract = OwnContract.objects(id=contract).get()
    if not ready_to_create_task(contract, archive_type):
        return dict(state='pending')
    params = dict(
        inn=provider.inn,
        kpp=provider.kpp,
        number=contract.number,
        date_from=date_from,
        date_till=date_till,
        contract_id=contract.id,
        account=account,
        url=url,
    )
    if archive_type == 'act':
        get_reconciliation_archive.delay(**params)
    elif archive_type == 'bill':
        get_bill_and_invoice_archive.delay(**params)
    else:
        return dict(state='archive_type not "act" or "bill"')
    return dict(state='proceed')


def get_issuing_documents_state(contract_id, period):
    doc = OwnIssuedDocuments.objects(
        contract=contract_id,
        period=DateHelpFulls.begin_of_month(period)
    ).as_pymongo().first()
    return doc


def get_sent_nomenclature_state(service_id):
    doc = OwnSentNomenclatures.objects(
        service=service_id
    ).as_pymongo().first()
    return doc


def ready_to_create_task(contract: OwnContract, task_type: str):
    """
    Подготовка задачи запуску.
    1) Запрет создание опроса, если документ в работе
    2) Очищение полей от предыдущих результатов
    """

    document_block_condition = (
            contract.doc_stack
            and getattr(contract.doc_stack, task_type)
            and getattr(contract.doc_stack, task_type).state == 'wip'
    )
    if document_block_condition:
        return False

    # Важно создать поле если его нет и при этом не стереть ничего важного
    if contract.doc_stack:
        # Если есть поле с актом - меняем статус
        if getattr(contract.doc_stack, task_type):
            getattr(contract.doc_stack, task_type).state = 'wip'
            # Очищение предыдущего статуса
            getattr(contract.doc_stack, task_type).description = None
            # Удаление предыдущего файла
            file_ = getattr(contract.doc_stack, task_type)
            if file_.uuid:
                try:
                    delete_file_in_gridfs(file_.uuid)
                except DoesNotExist:
                    pass
                file_.uuid = None
        # Если нет - создаем поле с актом
        else:
            archive_body = ArchiveDocuments(state='wip')
            setattr(contract.doc_stack, task_type, archive_body)
    else:
        # Если нет вообще - создаем поле с документами и в нем акт
        contract.doc_stack = DocumentStackEmbedded(
            **{task_type: ArchiveDocuments(state='wip')}
        )
    contract.save()
    return True
