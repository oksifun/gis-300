# -*- coding: utf-8 -*-
import datetime

from mongoengine import DoesNotExist, Q

from app.area.models.area import ActorAreaEmbedded
from app.auth.models.actors import Actor, RoboActor
from app.auth.models.embeddeds import (
    AccountEmbedded, ConnectedActorEmbedded, SlugEmbedded
)
from app.house.models.house import ActorHouseEmbedded, House
from app.permissions.migrations.slug_permission import tab_mapper, \
    transform_permissions
from app.personnel.models.personnel import Worker
from processing.models.billing.account import Tenant
from processing.models.billing.base import BindsPermissions
from processing.models.billing.house_group import HouseGroup
from processing.models.billing.provider.embeddeds import ActorProviderEmbedded
from processing.models.billing.provider.main import Provider
from processing.models.permissions import Permissions, ClientTab
from utils.crm_utils import provider_can_access


def migrate_actors(logger):
    logger(f'{datetime.datetime.now()} сотрудники')
    pp_w = migrate_workers(logger)
    logger(f'{datetime.datetime.now()} жители')
    pp_t = migrate_tenants(logger)
    logger(f'{datetime.datetime.now()} объединение')
    connect_users(logger)
    logger(f'{datetime.datetime.now()} организации')
    providers = list(set(pp_w) | set(pp_t))
    logger(f'всего организаций к обработке {len(providers)}')
    migrate_providers(logger, providers)
    logger(f'{datetime.datetime.now()} готово')


def migrate_tenants(logger, house_from=None):
    providers = {}
    match_query = dict(
        _type='Tenant',
        has_access=True,
    )
    if house_from:
        match_query.update(area__house__id__gte=house_from)
    tenants = Tenant.objects(
        **match_query,
    ).order_by(
        'area.house._id',
    )
    tenants_count = tenants.count()
    logger(f'всего жителей к обработке {tenants_count}')
    tenant = tenants.first()
    house = House.objects(pk=tenant.area.house.id).get()
    print('house', house.pk)
    provider_id = house.get_provider_by_business_type('udo')
    provider = Provider.objects(pk=provider_id).get()
    parent = RoboActor.get_default_robot(provider.pk)
    providers[provider.pk] = parent
    for num, tenant in enumerate(tenants, start=1):
        if house.pk != tenant.area.house.id:
            try:
                house = House.objects(pk=tenant.area.house.id).get()
                print('house', house.pk)
                provider_id = house.get_provider_by_business_type('udo')
                if not provider_id:
                    logger(
                        f'не найдена УК жителя {tenant.pk}',
                    )
                    continue
                provider = Provider.objects(pk=provider_id).get()
                parent = RoboActor.get_default_robot(provider.pk)
                if not parent:
                    continue
                providers[provider.pk] = parent
            except DoesNotExist:
                logger(
                    f'не найден дом {tenant.area.house.id} жителя {tenant.pk}',
                )
                continue
        if not parent:
            continue
        create_actor(
            tenant,
            provider,
            tenant.email,
            [],
            {},
            house,
            providers[provider.pk].pk,
            active=True,
        )
        if num % 100 == 0:
            logger(f"{num}/{tenants_count}")
    return providers


def migrate_workers(logger, provider_id=None, remove_existing=False):
    if remove_existing and not provider_id:
        raise Exception('provider_id is required for remove_existing')
    providers = {}
    match_query = Q(
        _type='Worker',
        has_access=True,
    )
    if provider_id:
        match_query &= Q(provider__id=provider_id)
    workers = list(
        Worker.objects(
            match_query,
        ).order_by(
            'provider.id',
        ),
    )
    workers_count = len(workers)
    logger(f'всего сотрудников к обработке {workers_count}')
    provider = Provider.objects(pk=workers[0].provider.id).get()
    parent = RoboActor.get_default_robot(provider.pk)
    providers[provider.pk] = parent
    if remove_existing and provider_id:
        removed = Actor.objects(
            provider__id=provider_id,
            owner__owner_type='Worker',
        ).delete()
        print('удалено', removed)
    for num, worker in enumerate(workers, start=1):
        try:
            old_perms = Permissions.objects(actor_id=worker.pk).get()
        except DoesNotExist:
            logger(
                f'не найдены права сотрудника {worker.pk}'
            )
            continue
        if provider.pk != worker.provider.id:
            try:
                provider = Provider.objects(pk=worker.provider.id).get()
            except DoesNotExist:
                logger(
                    f'не найдена организация {worker.provider.id} '
                    f'сотрудника {worker.pk}',
                )
                continue
            parent = RoboActor.get_default_robot(provider.pk)
            if not parent:
                continue
            providers[provider.pk] = parent
        if not parent:
            continue
        actor = Actor.get_or_create_actor_by_worker(worker)
        tabs = tab_mapper()
        perms = transform_permissions(old_perms, tabs)
        actor.permissions = perms
        if num % 10 == 0:
            logger(f"{num}/{workers_count}")
    return providers


def migrate_providers(logger, provider_id=None):
    if provider_id:
        providers = Provider.objects(pk=provider_id)
    else:
        providers = Provider.objects(crm_status='client')
    for provider in providers:
        create_bot(provider, get_slugs(provider.pk))


def create_actor(account, provider, username, slugs, binds, house, parent_id,
                 active):
    account_type = account._type[-1]
    actor = Actor(
        provider=ActorProviderEmbedded(
            id=provider.pk,
            str_name=provider.str_name,
            inn=provider.inn,
            client_access=provider_can_access(provider.pk),
        ),
        parent=parent_id,
        connected=[],
        is_super=getattr(account, 'is_super', False),
        slugs=slugs,
        binds_permissions=binds,
        username=username,
        password=account.password,
        has_access=account.has_access,
        get_access_date=account.get_access_date,
        sessions=[],
        active=active,
    )
    if account_type == 'Tenant':
        actor.owner = AccountEmbedded.from_tenant(
            account,
            Actor.get_house_business_types(house),
        )
    else:
        actor.owner = AccountEmbedded.from_worker(account)
    if account.activation_code:
        actor.activation_code = account.activation_code
    if account.activation_step:
        actor.activation_step = account.activation_step
    if account.activation_tries:
        actor.activation_tries = account.activation_tries
    if account.password_reset_code:
        actor.password_reset_code = account.password_reset_code
    actor.save()
    return actor


def create_bot(provider, slugs):
    actor = RoboActor(
        provider=ActorProviderEmbedded(
            id=provider.pk,
            str_name=provider.str_name,
            inn=provider.inn,
            client_access=provider_can_access(provider.pk),
        ),
        default=True,
        slugs=slugs,
        binds_permissions=_generate_provider_binds(provider),
        active=True,
        sessions=[],
    )
    actor.save()
    return actor


def _generate_provider_binds(provider):
    house_groups = HouseGroup.objects(
        provider=provider.pk,
        is_deleted__ne=True,
    ).only('id', 'houses').as_pymongo()
    max_group = {'houses': [], '_id': None}
    for house_group in house_groups:
        if not house_group.get('houses'):
            continue
        if len(house_group['houses']) > len(max_group['houses']):
            max_group = house_group
    return BindsPermissions(
        pr=provider.pk,
        hg=max_group['_id'],
    )


def get_slugs(actor_id):
    try:
        user_permissions = Permissions.objects(
            actor_id=actor_id,
        ).as_pymongo().get()
        tabs = list(ClientTab.objects.as_pymongo())
    except DoesNotExist:
        return []
    results = []
    for tab in tabs:
        if 'Tab' not in user_permissions['granular']:
            continue
        if str(tab['_id']) in user_permissions['granular']['Tab']:
            perm = user_permissions['granular']['Tab'][str(tab['_id'])]
            if perm:
                results.append(
                    SlugEmbedded(
                        slug=tab['slug'],
                        c=perm[0]['permissions'].get('c'),
                        r=perm[0]['permissions'].get('r'),
                        u=perm[0]['permissions'].get('u'),
                        d=perm[0]['permissions'].get('d'),
                    ),
                )
    return results


def connect_users(logger):
    actors = Actor.objects(_type='Actor')
    emails = {}
    for actor in actors._iter_results():
        data = emails.setdefault(actor.owner.email, [])
        data.append(actor)
    u = 0
    for email, actors in emails.items():
        if len(actors) <= 1:
            continue
        for actor in actors:
            actor.connected = []
            u += 1
            for other_actor in [a for a in actors if a.pk != actor.pk]:
                actor.connected.append(
                    ConnectedActorEmbedded(
                        id=other_actor.pk,
                        owner=other_actor.owner,
                        provider=other_actor.provider,
                    )
                )
            actor.save()
    logger(f'объединено {u}')
