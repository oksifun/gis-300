from bson import ObjectId

from processing.data_producers.associated.base import get_binded_houses
from processing.models.billing.account import Tenant
from processing.models.logging.custom_scripts import CustomScriptData


def mask_personal_data(logger, task, provider_id):
    """
    Masks personal data (last name for people and name for organisations) and
    backups current:

    A -> A*****A
    AB -> A*****B
    ABC -> AB*****C
    ABCD -> AB*****D
    etc.

    :param logger: logger function for logging actions
    :param task: task which started this script
    :param provider_id: organisation id
    :return: nothing
    """

    def mask_str(str):
        mask = '*****'
        return f'{str[0:2]}{mask}{str[-1:]}'

    provider_id = ObjectId(provider_id)
    houses = get_binded_houses(provider_id)
    match_query = {"area.house._id": {"$in": houses}}
    tenants = Tenant.objects(__raw__=match_query)
    logger('Нашла {} жильцов'.format(tenants.count()))
    # CustomScriptData(
    #     task=task.id if task else None,
    #     coll='Tenant',
    #     data=list(tenants.as_pymongo())
    # ).save()
    counter = 0
    for tenant in tenants._iter_results():
        if 'PrivateTenant' in tenant._type:
            tenant.last_name = mask_str(tenant.last_name)
            counter += 1
        elif 'LegalTenant' in tenant._type:
            tenant.name = mask_str(tenant.name)
            counter += 1
        tenant.save()
    logger(f'Замаскировала {counter} жителей')
