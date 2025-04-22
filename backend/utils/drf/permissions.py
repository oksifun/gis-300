from typing import Optional
from mongoengine import DoesNotExist
from rest_framework import permissions

import settings
from app.auth.models.actors import SessionEmbedded, Actor, RoboActor
from app.personnel.models.personnel import Worker
from processing.models.billing.session import Session
from processing.models.billing.account import Tenant
from processing.models.permissions import Permissions, ClientTab
from processing.models.billing.provider.main import Provider

CRUD_ACTIONS = {
    'list': 'r',
    'retrieve': 'r',
    'create': 'c',
    'partial_update': 'u',
    'destroy': 'd',
}
ALT_CRUD_ACTIONS = {
    'GET': 'r',
    'POST': 'c',
    'PATCH': 'u',
    'DELETE': 'd',
    'PUT': 'u',
}
ALL_CRUD_ACTIONS = {'c', 'r', 'u', 'd'}
READONLY_ACTIONS = {'r'}


class IsActorAuthenticated(permissions.BasePermission):
    def has_permission(self, request, view):
        authenticated = all((
            request.user,
            request.auth,
            isinstance(request.user, (Actor, RoboActor)),
            isinstance(request.auth, SessionEmbedded),
        ))
        if not authenticated:
            return False
        if (
                not hasattr(view, 'slug')
                or getattr(request.user, 'is_super', False)
        ):
            return True
        action = (
                CRUD_ACTIONS.get(view.action)
                or ALT_CRUD_ACTIONS.get(request.method)
        )
        permit = getattr(view, 'allow_creating_tasks_as_retrieve', None)
        if permit:
            action = 'read'
        slugs = self.normalize_slugs(view.slug, action)
        return any(
            request.user.has_perm(slug, action) for slug in slugs
        )

    @staticmethod
    def normalize_slug(slug, action) -> Optional[str]:
        if type(slug) is dict and action in slug['actions']:
            return slug['name']
        if type(slug) is str:
            return slug

    def normalize_slugs(self, slug, action) -> set:
        if type(slug) is str:
            return {slug}
        if type(slug) in (list, tuple):
            return {self.normalize_slug(k, action) for k in slug} - {None}


class IsAuthenticated(permissions.BasePermission):
    def has_permission(self, request, view):
        authenticated = all(
            (
                request.user,
                request.auth,
                isinstance(request.user, Worker)
                or isinstance(request.user, Tenant),
                isinstance(request.auth, Session),
            )
        )
        if not authenticated:
            return False
        if not hasattr(view, 'slug') or request.user.is_super:
            return True
        try:
            user_permissions = Permissions.objects(
                actor_id=request.user.pk,
            ).as_pymongo().get()
            tabs = self._get_tab_permisions_by_slug_description(view.slug)
        except DoesNotExist:
            return False
        action = (
                CRUD_ACTIONS.get(view.action)
                or ALT_CRUD_ACTIONS.get(request.method)
        )
        for tab_id, data in tabs.items():
            if not action or action not in data['actions']:
                continue
            perm = user_permissions['granular']['Tab'].get(tab_id)
            if not perm:
                continue
            if hasattr(view, 'allow_creating_tasks_as_retrieve'):
                if (
                        view.allow_creating_tasks_as_retrieve
                        and perm[0]['permissions'].get('r')
                ):
                    return True
            if perm[0]['permissions'].get(action):
                return True
        return False

    @staticmethod
    def _get_tab_permisions_by_slug_description(slug):
        if isinstance(slug, tuple) or isinstance(slug, list):
            slugs = slug
        else:
            slugs = [slug]
        result = {}
        for s in slugs:
            if isinstance(s, dict):
                result[s['name']] = s
            else:
                result[s] = {'name': s, 'actions': ALL_CRUD_ACTIONS}
        tabs = list(
            ClientTab.objects(
                slug__in=list(result.keys()),
            ).only(
                'id',
                'slug',
            ).as_pymongo(),
        )
        return {
            str(tab['_id']): result[tab['slug']]
            for tab in tabs
        }


class SuperActorOnly(permissions.BasePermission):
    """Выдает право только для суперпользователя"""
    def has_permission(self, request, view):
        user = request.user
        if getattr(user, 'is_super'):
            return True
        return Actor.objects(session__id=request.auth.id).get().is_super


class SuperUserOnly(permissions.BasePermission):
    """Выдает право только для суперпользователя"""
    def has_permission(self, request, view):
        user = request.user
        if hasattr(user, 'is_super'):
            return user.is_super
        return False


class TelephonyPermission(permissions.BasePermission):
    """Проверяет есть ли доступ к синхронизации телефонии"""
    def has_permission(self, request, view):
        token = request.META.get("HTTP_TOKEN", "")
        provider = Provider.objects(telephony_settings__token=token).first()
        if provider:
            return True
        return False


class SuperUserOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        if getattr(request.user, 'is_super'):
            return True
        return False
