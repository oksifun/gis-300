import copy
from datetime import datetime

from dateutil.relativedelta import relativedelta
from mongoengine import Q

from app.auth.models.actors import Actor
from lib.helpfull_tools import by_mongo_path
from app.accruals.cipca.source_data.areas import get_property_share, \
    get_responsibles
from processing.models.billing.account import Tenant
from processing.models.billing.family_role_catalogue import FamilyRoleCatalogue
from processing.models.billing.responsibility import Responsibility


class TenantExtraException(Exception):
    pass


def get_extra_tenant_data(provider_id, tenant_id, binds):
    """
    Получение дополнительных данных по жителю вроде является ли ответсвенным
    или может ли логиниться
    """
    tenant = Tenant.objects(
        Tenant.get_binds_query(binds),
        pk=tenant_id,
    ).only(
        'id',
        'area.id',
        'statuses',
        'has_access',
        'activation_code',
        'activation_step',
        'family',
    ).as_pymongo().get()

    result = {
        'blocked': (tenant.get('activation_step') or 0) >= 5,
        'activated': is_activated(tenant),
        'is_owner': False,
        'can_login': can_login(tenant),
        'is_responsible': False,
        'registered_from': None,
        'living_from': None,
        'registered': False,
        'living': False,
        'family': get_family(tenant, binds, provider_id),
    }

    dtn = datetime.now()
    if tenant.get('statuses'):
        ownership = tenant['statuses'].get('ownership') or {}
        for r in tenant['statuses'].get('registration', []) or []:
            if (
                    (r.get('date_from') or dtn)
                    <= dtn
                    <= (r.get('date_till') or dtn)
            ):
                result['registered'] = True
                result['registered_from'] = r['date_from']
                break
        for r in tenant['statuses'].get('living', []) or []:
            if (
                    (r.get('date_from') or dtn)
                    <= dtn
                    <= (r.get('date_till') or dtn)
            ):
                result['living'] = True
                result['living_from'] = r['date_from']
                break
    else:
        ownership = {}
    started_at = ownership.get('started_at')
    is_owner = ownership.get('is_owner', False)
    responsibles = _get_responsible(provider_id, tenant)
    result['is_responsible'] = tenant_id in responsibles
    for mate in result['family']:
        mate['is_responsible'] = mate['id'] in responsibles
    result['is_owner'] = (
        (is_owner and not started_at)
        or (dtn > started_at if started_at else False)
    )
    return result


def get_tenant_coefs_on_date(tenant, coefs, on_date):
    result = {}
    sorted_coefs = sorted(
        tenant.get('coefs', []),
        key=lambda x: x['period'],
        reverse=True
    )
    for coef in sorted_coefs:
        coef_id = coef['coef']
        # coef_number = coef['reason'].get(  'number')
        if coef_id not in coefs:
            continue

        is_once = coefs[coef_id]['is_once']
        coef['title'] = coefs[coef_id]['title']
        period_condition = (
                not is_once and coef['period'] <= on_date
                or is_once and coef['period'] == on_date
        )
        if period_condition and coef_id not in result:
            result[coef_id] = coef

    return result


def is_mate_owner(mate):
    statuses = mate.get('statuses', {})
    if not statuses:
        return False
    ownership = statuses.get('ownership', {})
    if not ownership:
        return False
    return ownership.get('is_owner', False)


def mate_serializer(tenant, date_on=None, responsibles_ids=None,
                    include_archive=True):
    if not date_on:
        date_on = datetime.now()
    if not responsibles_ids:
        responsibles_ids = []
    mate = copy.deepcopy(tenant)
    mate['phones'] = [
        dict(
            code=x.get('code', ''),
            number=x.get('number', ''),
            add=x.get('add', ''),
            phone_type=x.get('type', ''),
            not_actual=x.get('not_actual', ''),
        )
        for x in mate.get('phones', [])
    ]
    mate['email'] = mate.get('email', '')
    mate['registered'] = False
    mate['living'] = False
    mate['is_owner'] = is_mate_owner(mate)
    mate['is_renter'] = False
    mate['is_responsible'] = mate['_id'] in responsibles_ids
    mate['id'] = mate.pop('_id')
    mate['is_coop_member'] = mate.get('is_coop_member') or False
    mate['ownership'] = (mate.get('statuses') or {}).get('ownership')
    if not mate.get('statuses'):
        if 'statuses' in mate:
            mate.pop('statuses')
        mate['is_archive'] = False
        return mate

    mate['is_archive'] = tenant_is_archive(mate, date_on)
    if mate['is_archive'] and not include_archive:
        return None

    for r in by_mongo_path(mate, 'statuses.registration', []):
        if _is_time_condition(r, date_on):
            mate['registered'] = True
            break

    for r in by_mongo_path(mate, 'statuses.living', []):
        if _is_time_condition(r, date_on):
            mate['living'] = True
            break

    if mate['statuses'].get('ownership'):
        share = get_property_share(
            mate['statuses']['ownership'].get('property_share_history', []),
            date_on,
            raw=True,
        )
        if share[0] > 0:
            if mate['statuses']['ownership']['type'] == 'private':
                mate['is_owner'] = True
            else:
                mate['is_renter'] = True
            mate['property_share'] = share
    confirm_tenant_archivation(mate)
    mate.pop('statuses')
    mate['has_access'] = mate.get('has_access')
    return mate


def get_family(tenant, binds, provider_id,
               include_self=False, include_archive=False):
    if not tenant.get('family'):
        return []

    responsibles = _get_responsible(provider_id, tenant)
    mates = _get_mates(tenant, binds)

    result = []
    now = datetime.now()
    if not include_self:
        mates = [m for m in mates if m['_id'] != tenant['_id']]
    for mate in mates:
        mate = mate_serializer(mate, now, responsibles)
        if mate:
            result.append(mate)

    add_roles_info(for_whom=tenant['_id'], data=result)
    return sorted(
        result,
        key=lambda i: (
            i['is_archive'],
            not i['is_responsible'],
            i['str_name'],
        ),
    )


def get_responsibility_in_date(tenant, period: datetime, provider):
    """
    Функция ищет ответсвенного жителя в переданный период
    :param tenant: проверяемый житель
    :param period: период, в которым нужно искать ответсвенного
    :param provider: текущий провайдер
    :return: True если остветсвенный обнаружен
    """
    date = Q(date_till__gte=period) | Q(date_till=None)
    date &= Q(date_from__lt=(period + relativedelta(months=1))) | Q(date_from=None)
    responsibility = Responsibility.objects(
        date,
        account__id=tenant,
        provider=provider,
    ).first()
    if responsibility:
        return True


def tenant_is_archive(tenant, date_on):
    if not tenant.get('statuses'):
        return False

    if not tenant['statuses'].get('accounting'):
        return False

    accounting = tenant['statuses']['accounting']
    if accounting.get('date_from') and accounting['date_from'] >= date_on:
        return True

    if accounting.get('date_till') and accounting['date_till'] <= date_on:
        return True

    return False


def confirm_tenant_archivation(tenant):
    if not tenant['is_archive']:
        archive_condition = all((
            not tenant['is_responsible'],
            not tenant['registered'],
            not tenant['living'],
            not tenant['is_owner']
        ))
        if archive_condition:
            tenant['is_archive'] = True


def can_login(tenant):
    return (
            tenant.get('has_access', False)
            and tenant.get('activation_code') is None
            and tenant.get('activation_step') is None
    )


def is_activated(tenant):
    actor = Actor.objects(owner__id=tenant['_id']).first()
    return actor.has_access if actor else False


def add_roles_info(for_whom, data):
    tenants_ids = [x['id'] for x in data]
    roles = FamilyRoleCatalogue.get_family_roles(tenants_ids)
    for tenant in data:
        tenants_roles = roles.get(tenant['id'])
        if not tenants_roles:
            continue
        reverse_role = tenants_roles.get(for_whom)
        if reverse_role:
            tenant['reverse_role'] = reverse_role['role']


def _get_responsible(provider_id, tenant):
    responsible = get_responsibles(
        provider_id=provider_id,
        areas_ids=[tenant['area']['_id']],
        date_on=datetime.now(),
    )
    return responsible.get(tenant['area']['_id'], [])


def _get_mates(tenant, binds):
    householder = (
        tenant['family']['householder']
        if tenant.get('family') and tenant['family'].get('householder')
        else tenant['_id']
    )
    return list(
        Tenant.objects.as_pymongo().filter(
            Tenant.get_binds_query(binds),
            area__id=tenant['area']['_id'],
            _type__in=['PrivateTenant', 'LegalTenant'],
            family__householder=householder,
            is_deleted__ne=True,
        ).only(
            'id',
            '_type',
            'str_name',
            'statuses',
            'sex',
            'is_coop_member',
            'phones',
            'email',
            'has_access',
        )
    )


def _is_time_condition(obj, dtn):
    return (obj.get('date_from') or dtn) <= dtn <= (obj.get('date_till') or dtn)
