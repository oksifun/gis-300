from app.area.models.area import Area
from app.house.models.house import House
from processing.models.billing.business_type import BusinessType
from processing.models.billing.provider.main import Provider


def sync_responsibility_to_providers(responsibility,
                                     only_from_udo=False, by_id=False):
    house = House.objects(pk=responsibility.account.area.house.id).get()
    if only_from_udo:
        need_to_sync = False
        udo = BusinessType.objects(slug__in=['udo', 'cс']).distinct('id')
        for service_bind in house.service_binds:
            if (
                    service_bind.is_active
                    and service_bind.provider == responsibility.provider
                    and service_bind.business_type in udo
            ):
                need_to_sync = True
        if not need_to_sync:
            return
    providers_to_sync = []
    # providers_to_sync_only_update = []
    for service_bind in house.service_binds:
        if service_bind.provider == responsibility.provider:
            continue
        provider = Provider.objects(pk=service_bind.provider).first()
        if not provider:
            continue
        if not only_from_udo or service_bind.sync_responsibles_from_udo:
            # if not service_bind.is_active:
            #     providers_to_sync_only_update.append(provider)
            # else:
            providers_to_sync.append(provider)
    if providers_to_sync:
        if by_id:
            responsibility.sync_responsibility(
                [
                    p.id for p in providers_to_sync
                ],
            )
        else:
            area = Area.objects(pk=responsibility.account.area.id).get()
            provider_from = Provider.objects(pk=responsibility.provider).get()
            for provider_to in providers_to_sync:
                responsibility.sync_by_areas(
                    [area],
                    provider_from,
                    provider_to,
                )


def get_responsibles_by_house(provider_id, house_id, date_on, date_till):
    from processing.models.billing.responsibility import Responsibility
    resp = Responsibility.objects.as_pymongo().filter(
        __raw__={
            'account.area.house._id': house_id,
            'provider': provider_id,
            '$and': [
                {
                    '$or': [
                        {'date_from': None},
                        {'date_from': {'$lt': date_till}}
                    ],
                },
                {
                    '$or': [
                        {'date_till': None},
                        {'date_till': {'$gte': date_on}}
                    ],
                },
            ],
        },
    ).distinct('account._id')
    return resp
