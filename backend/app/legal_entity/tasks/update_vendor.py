import logging

from bson import ObjectId

from app.celery_admin.workers.config import celery_app
from app.legal_entity.models.logs import VendorServiceApplyLog
from app.offsets.models.offset import Offset
from processing.models.billing.accrual import Accrual

ADVANCE_ID = ObjectId('1' * 24)
PENALTY_ID = ObjectId('0' * 24)

logger = logging.getLogger(__name__)


def push_contract_to_offsets_advance_and_penalties(service, service_type,
                                                   test_mode,
                                                   offset_type=None):
    """
    Обновление поля services.vendor только тех Offset,
    у которых или _type = 'Advance'
    или select_service_type в договоре 'penalties'
    """
    date_match = {'$gte': service.date_from}
    if service.date_till:
        date_match.update({'$lte': service.date_till})
    query = {
        'refer.account.area.house._id': service.house,
        'services.service_type': service_type,
        'refer.doc.date': date_match,
    }
    if offset_type:
        query.update({'_type': offset_type})
    query_set = Offset.objects(__raw__=query)
    if test_mode:
        result = query_set.count()
    else:
        result = query_set.update(
            __raw__={
                '$set': {
                    'services.$.vendor': {
                        '_id': service.entity,
                        'contract': service.contract,
                    },
                },
            },
        )
    logger.info(f'Found {query_set.count()} Offsets (penalties/advances)')
    print(f'Found {query_set.count()} Offsets (penalties/advances)')
    return result


def push_penalty_vendor_to_accrual(service, test_mode):
    """
    Обновление поля penalty_vendor в Accrual для тех договоров,
    у которых service_select_type = 'penalties'
    """
    date_match = {'$gte': service.date_from}
    if service.date_till:
        date_match.update({'$lte': service.date_till})
    query_set = Accrual.objects(
        __raw__={
            'account.area.house._id': service.house,
            'month': date_match
        },
    )
    if test_mode:
        result = query_set.count()
    else:
        result = query_set.update(
            __raw__={
                '$set': {
                    'penalty_vendor': {
                        '_id': service.entity,
                        'contract': service.contract,
                    },
                },
            },
        )
    logger.info(f'Found {query_set.count()} Accruals (penalties)')
    print(f'Found {query_set.count()} Accruals (penalties)')
    return result


def push_contract_to_accrual_service(service, test_mode):
    date_match = {'$gte': service.date_from}
    if service.date_till:
        date_match.update({'$lte': service.date_till})
    query_set = Accrual.objects(
        __raw__={
            'account.area.house._id': service.house,
            'services.service_type': service.service,
            'month': date_match,
        }
    )
    if not test_mode:
        query_set.update(
            __raw__={
                '$set': {
                    'services.$.vendor': {
                        '_id': service.entity,
                        'contract': service.contract,
                    },
                },
            },
        )
    logger.info(f'Found {query_set.count()} regular Accruals')
    print(f'Found {query_set.count()} regular Accruals')
    return [item.id for item in query_set]


def push_contract_to_offset_service(service, accrual_ids, test_mode):
    """
    На основе id Accrual обновляются записи services.vendor в Offset
    """
    query_set = Offset.objects(
        accrual__id__in=accrual_ids,
        services__service_type=service.service,
    )
    result = 0
    if not test_mode:
        result = query_set.update(
            __raw__={
                '$set': {
                    'services.$.vendor': {
                        '_id': service.entity,
                        'contract': service.contract,
                    },
                },
            },
        )
    logger.info(f'Found {query_set.count()} regular Offsets')
    print(f'Found {query_set.count()} regular Offsets')
    return result


@celery_app.task(
    soft_time_limit=60 * 5,
    bind=True,
    rate_limit='30/m',
    max_retries=5,
    default_retry_delay=120,
)
def vendor_apply_to_offsets(self, service_id, test_mode=False,
                            skip_offsets=False, delete_mode=False):
    """
    Функция для обновления поля vendor в services у Accrual, Offset
    при сохранении LegalEntityContract
    """
    from app.legal_entity.models.legal_entity_service import \
        EntityAgreementService
    service = EntityAgreementService.objects(pk=service_id).get()
    service_desc = f'{service_id} ' \
                   f'({service.service_select_type}: {service.service})'
    VendorServiceApplyLog.write_log(
        service.entity,
        f'vendor_apply_to_offsets starts for service {service_desc}',
    )
    if delete_mode:
        # Удаляет поле contract из Offset и Accrual
        service.contract = None
    if service.service_select_type == 'penalties':
        if not skip_offsets:
            push_contract_to_offsets_advance_and_penalties(
                service, PENALTY_ID, test_mode
            )
        push_penalty_vendor_to_accrual(service, test_mode)
    elif service.service_select_type == 'advance' and not skip_offsets:
        offset_type = 'Advance'
        push_contract_to_offsets_advance_and_penalties(
            service, ADVANCE_ID, test_mode, offset_type=offset_type)
    else:
        accrual_ids = push_contract_to_accrual_service(service, test_mode)
        if accrual_ids and not skip_offsets:
            push_contract_to_offset_service(service, accrual_ids, test_mode)
    VendorServiceApplyLog.write_log(
        service.entity,
        f'vendor_apply_to_offsets finished for service {service_desc}',
    )
