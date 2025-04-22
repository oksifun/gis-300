from api.v4.authentication import RequestAuth
from api.v4.viewsets import BaseLoggedViewSet
from app.permissions.api.v4.serializers import TabAvailableSerializer
from processing.models.permissions import ClientTab, Permissions
from settings import ZAO_OTDEL_PROVIDER_OBJECT_ID


class TabAvailableViewSet(BaseLoggedViewSet):

    """
    Контроллер для определения прав на кнопку
    Запрашиваются права юзера, если он есть, и организации
    Конечно право определяется логическим умножением прав организации на права
    сотрудника по каждому элементу
    """

    @staticmethod
    def get_tab_permission(permission, children_tab):
        """
        Возврщает право на кнопку для любого actor
        Если прав нет, возращает False, для умножения прав внутри организации
        :param permission: права
        :param children_tab: кнопка, на которую запршиваются права
        :return:
        """

        tab_perm = permission['granular']['Tab'].get(str(children_tab))
        if tab_perm:
            return tab_perm[0].get('permissions', {}).get('r', False)
        else:
            return False

    def return_permission(self, permission, children_tabs, provider_permission):
        """
        Для вычислиения итогового парва на кнопку, права actor и организации
        логически перемножаются. Это позволяет исключить возможность
        использовать кнопку, если на уровне организации это запрещено, хоть
        и у actor есть права на кнопку

        :param permission: права actor (им может быть и организация)
        :param children_tabs: список кнопок
        :param provider_permission: обязательные права организации
        :return:
        """
        return any([
            self.get_tab_permission(permission, children_tab['_id']) *
            self.get_tab_permission(provider_permission, children_tab['_id'])
            for children_tab in children_tabs
        ])

    def get_self_permission(self, permission, provider_permission, tab_id):
        return self.get_tab_permission(permission, tab_id) * \
               self.get_tab_permission(provider_permission, tab_id)

    @staticmethod
    def get_permission(query_string):
        """
        возращает queryset прав для любого вида юзера, будто оргназация или
        работник
        :param query_string: пармеметр запроса
        """
        return Permissions.objects(
            _id=query_string
        ).as_pymongo().only('granular.Tab').first()

    def list(self, request):
        serializer = TabAvailableSerializer(data=request.query_params)
        request_auth = RequestAuth(request)
        provider_id = request_auth.get_provider_id()
        tabs_list = serializer.get_param('tabs_list')
        user = request_auth.get_account()

        actor_atr = {
            True: ('Account', getattr(user, 'id', None)),
            False: ('Provider', provider_id)
        }
        actor, actor_id = actor_atr[bool(user)]
        query_string = f'{actor}:{str(actor_id)}'
        permission = self.get_permission(query_string)
        provider_permission = self.get_permission(f'Provider:{str(provider_id)}')
        tabs_response = []

        for tab_id in tabs_list:
            underline = False
            self_permission = self.get_self_permission(
                permission, provider_permission, tab_id
            )
            if (
                request_auth.is_super()
                and provider_id == ZAO_OTDEL_PROVIDER_OBJECT_ID
            ):
                resp = True
            else:
                children_tabs = ClientTab.objects(
                    parent=tab_id
                ).as_pymongo().only('promo_url')

                has_promo_urls = any(
                    [tab.get('promo_url') for tab in children_tabs]
                )

                if (
                    not permission
                    or not permission.get('granular')
                    or not permission['granular'].get('Tab')
                ):
                    has_permission = False
                else:
                    has_permission = self.return_permission(
                        permission, children_tabs, provider_permission
                    )
                resp = bool(has_promo_urls + has_permission + self_permission)
                if has_promo_urls and not bool(has_permission + self_permission):
                    underline = True

            tabs_response.append(
                {
                    'tab': tab_id,
                    'show': resp,
                    'underline': underline
                }
            )

        return self.json_response(tabs_response)
