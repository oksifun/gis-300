from app.crm.models.crm import CRM, CRMStatus, ProviderDenormalized
from app.crm.models.crm import CAN_TENANT_ACCESS_STATUS
from processing.models.billing.provider.main import Provider
from settings import ZAO_OTDEL_PROVIDER_OBJECT_ID


def get_crm_client_ids(owner=ZAO_OTDEL_PROVIDER_OBJECT_ID,
                       include_debtors=False):
    status = 'client'
    if include_debtors:
        status = {'$in': ['client', 'debtor']}
    return CRM.objects(
        __raw__={
            'status': status,
            'owner': owner,
        },
    ).distinct(
        'provider._id',
    )


def filter_crm_clients_by_provider_id(provider_ids,
                                      owner=ZAO_OTDEL_PROVIDER_OBJECT_ID,
                                      include_debtors=False):
    status = 'client'
    if include_debtors:
        status = {'$in': ['client', 'debtor']}
    query = {
        'owner': owner,
        'status': status,
        'provider._id': {'$in': provider_ids},
    }
    return CRM.objects(
        __raw__=query,
    ).distinct(
        'provider._id',
    )


def get_owner_relations(owner_id):
    return CRM.objects(
        owner=owner_id,
    )


def get_relations_with_providers(owner_id, provider_ids):
    return list(
        CRM.objects(
            owner=owner_id,
            provider__id__in=provider_ids,
        ).as_pymongo(),
    )


def get_providers_ids_with_statuses(owner_id, status_list):
    return CRM.objects(
        owner=owner_id,
        status__in=status_list,
    ).distinct("provider.id")


def get_two_providers_relation(owner_id, provider_id):
    return CRM.objects(
        owner=owner_id,
        provider__id=provider_id,
    ).first()


def _initialize_relation(owner_id, provider_id):
    provider = Provider.objects(pk=provider_id).get()
    provider_denormalized = ProviderDenormalized.from_ref(provider)
    crm_obj = CRM(
        owner=owner_id,
        status=CRMStatus.NEW,
        provider=provider_denormalized,
    )
    crm_obj.save()
    return crm_obj


def get_or_create_relation_between_two_providers(owner_id, provider_id):
    relation = get_two_providers_relation(owner_id, provider_id)
    if not relation:
        relation = _initialize_relation(owner_id, provider_id)
    return relation


def is_zao_otdel_client(provider_id):
    _relation = get_or_create_relation_between_two_providers(
        ZAO_OTDEL_PROVIDER_OBJECT_ID,
        provider_id,
    )
    return _relation.status == CRMStatus.CLIENT


def provider_has_status(provider_id, status):
    relation = CRM.objects(
        owner=ZAO_OTDEL_PROVIDER_OBJECT_ID,
        provider__id=provider_id,
        status=status,
    ).only(
        'status',
    ).hint(
        'provider_crm_status',
    ).as_pymongo().first()
    return relation['status'] == status if relation else False


def provider_can_access(provider_id):
    return (
            provider_has_status(provider_id, CRMStatus.CLIENT)
            or provider_has_status(provider_id, CRMStatus.ARCHIVE)
    )


def provider_can_tenant_access(provider_id):
    """
    Функция для выдачи доступа жителям в зависимости от статуса организации.
    """
    relation = CRM.objects(
        owner=ZAO_OTDEL_PROVIDER_OBJECT_ID,
        provider__id=provider_id,
        status__in=CAN_TENANT_ACCESS_STATUS,
    ).only('status').as_pymongo().first()
    return bool(relation)


def update_actors_access(provider_id):
    from app.auth.models.actors import Actor

    can_tenant_access = provider_can_tenant_access(provider_id)
    actors = Actor.objects(provider__id=provider_id)
    actors.update(provider__client_access=can_tenant_access)
