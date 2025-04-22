from bson import ObjectId
from mongoengine import Q

from processing.models.billing.provider.main import Provider
from app.personnel.models.personnel import Worker
from app.personnel.models.department import Department
from utils.crm_utils import get_relations_with_providers


def get_provider_departments(provider_id):
    departments = list(Department.objects(provider=provider_id).as_pymongo())
    return departments


def get_providers_where_account_is_decision_maker(
        owner_id, provider_id, codes
):
    decision_maker = Worker.objects(
        provider__id=provider_id,
        position__code__in=codes,
        is_deleted__ne=True,
        is_dismiss__ne=True
    ).only(
        'email', 'phones', 'last_name', 'first_name', 'patronymic_name'
    ).as_pymongo().first()
    providers_ids_for_decision_maker = map(
        lambda w: w['provider']['_id'],
        _get_similar_decision_makers(decision_maker)
    )
    providers_for_decision_maker = Provider.objects(
        id__in=list(providers_ids_for_decision_maker),
        id__ne=provider_id
    ).only(
        'str_name', 'address', 'business_types',
        'postal_address', 'real_address', 'id'
    )
    statuses = {
        s['provider']['_id']: s['status']
        for s in get_relations_with_providers(
            owner_id,
            [p.id for p in providers_for_decision_maker])
    }
    for p in providers_for_decision_maker:
        p.crm_status = statuses.get(p.id, 'new')
    return providers_for_decision_maker


def _get_similar_decision_makers(worker):
    """ Функция для поиска похожих аккаунтов, которые являются ЛПР в какой-либо
    организации
    Args:
        worker:
            Worker в виде словаря
    Return:
        Список аккаунтов
    """
    if not worker:
        return []

    query = []
    phones = []

    for phone in worker.get('phones') or []:
        if phone.get('number'):
            phones.append(
                {
                    'code': phone.get('code'),
                    'add': phone.get('add'),
                    'number': phone.get('number'),
                }
            )

    if phones:
        query.append(
            {
                'phones': {
                    '$elemMatch': {
                        '$or': phones
                    }
                }
            }
        )

    if worker.get('email'):
        query.append(
            {'email': worker['email']}
        )

    if not query:
        return []

    spec = {
        '$or': query,
        '$and': [
            {
                'position.code': {
                    '$in': ['ch1', 'ch2', 'ch3', 'acc1']
                }
            },
            {
                'is_dismiss': {
                    '$ne': True
                }
            }
        ]
    }

    if worker.get('last_name'):
        spec['$and'].append(
            {
                'last_name': {
                    '$regex': '^{}'.format(worker['last_name']),
                    '$options': 'i'
                }
            }
        )

        if worker.get('first_name'):
            spec['$and'].append(
                {
                    'first_name': {
                        '$regex': '^{}'.format(worker['first_name']),
                        '$options': 'i'
                    }
                }
            )

        if worker.get('patronymic_name'):
            spec['$and'].append(
                {
                    'patronymic_name': {
                        '$regex': '^{}'.format(worker['patronymic_name']),
                        '$options': 'i',
                    }
                }
            )
    same_workers = list(
        Worker.objects(
            __raw__=spec,
            is_deleted__ne=True,
        ).only('provider').as_pymongo()
    )

    return same_workers
