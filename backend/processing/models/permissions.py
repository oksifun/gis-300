from bson import ObjectId

from mongoengine import Document, DictField, StringField, ObjectIdField, \
    BooleanField, ListField, ValidationError


def _not_contain_point(value):
    try:
        value.index('.')
    except ValueError:
        pass
    else:
        raise ValidationError("Field can't contain point.")


class Permissions(Document):
    """
    Прототип модели для получения прав
    из соответствующей коллекции, работает через as_pymongo()
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Permissions',
    }
    actor_id = ObjectIdField()

    _id = StringField()
    actor_type = StringField()
    current = DictField()
    granular = DictField()
    general = DictField()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from app.permissions.tasks.binds_permissions import sync_permissions
        sync_permissions.delay(self.actor_id)

    def transfer_to_actor(self):
        from app.auth.models.actors import Actor
        from app.personnel.models.personnel import Worker
        from app.auth.models.embeddeds import SlugEmbedded
        from app.permissions.migrations.slug_permission import \
            transform_permissions

        tabs = ClientTab.get_tabs_list()
        results = []
        for tab in tabs:
            if 'Tab' not in self.granular:
                continue
            if str(tab['_id']) in self.granular.get('Tab'):
                perm = self.granular.get('Tab').get(str(tab['_id']))
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
        worker_instance = Worker.objects(
            id=self.actor_id
        ).first()
        actor = Actor.get_or_create_actor_by_worker(worker_instance)
        actor.slugs = results

        tabs_dict = {str(tab['_id']): tab['slug'] for tab in tabs}
        perms = transform_permissions(self, tabs_dict)
        actor.permissions = perms
        actor.save()

    @classmethod
    def crud(cls, create=True, read=True, update=True, delete=True) -> dict:

        return {'c': create, 'r': read, 'u': update, 'd': delete}

    @classmethod
    def id_format(cls, _type: str, _id: ObjectId) -> str:

        return f"{_type}:{_id}"

    @classmethod
    def get_or_create(cls, _type: str, _id: ObjectId) -> 'Permissions':

        assert _type in {'BusinessType', 'Provider', 'Account'}
        permissions_id: str = cls.id_format(_type, _id)

        permissions: Permissions = cls.objects(__raw__={
            '_id': permissions_id  # индекс WARN _id не pk
        }).first()
        if permissions is None:
            permissions = Permissions(
                _id=permissions_id, actor_type=_type, actor_id=_id,
                current={'Tab': dict(allow={'c':[], 'r':[], 'u':[], 'd':[]})},
                granular={'Tab': {}},  # WARN обязательное поле, House - нет
                # TODO general = {} по умолчанию
            )

        assert isinstance(permissions.general, dict) and \
            isinstance(permissions.current, dict) and \
            isinstance(permissions.granular, dict)

        return permissions  # WARN без сохранения

    @classmethod
    def get_account_houses(cls, account_id: ObjectId) -> list:

        permissions: dict = cls.objects(__raw__={
            '_id': cls.id_format('Account', account_id)
        }).as_pymongo().only('_id', 'actor_id', 'granular.House').first()
        if permissions is not None:
            granular_houses: dict = permissions.get('granular', {}).get('House')
            if granular_houses:  # непустой словарь?
                return sorted(ObjectId(_id) for _id in granular_houses.keys())

        return []

    def allow_house(self, house_id: ObjectId,
            create=True, read=True, update=True, delete=True):

        permissions: dict = self.crud(create, read, update, delete)

        granular_house: dict = self.granular.setdefault('House', {})
        if create or read or update or delete:
            granular_house[str(house_id)] = [{'permissions': {
                act: var for act, var in permissions.items() if var  # без False
            }, '_id': ObjectId()}]
        elif granular_house.get(str(house_id), False):
            del granular_house[str(house_id)]  # WARN удаляем элемент

        current_house: dict = self.current.setdefault('House', {})
        allow: dict = current_house.setdefault('allow', {})

        for act, var in permissions.items():  # 'c','r','u','d'
            allowed: list = allow.setdefault(act, [])
            if var and house_id not in allowed:
                allowed.append(house_id)
            elif not var and house_id in allowed:
                allowed.remove(house_id)

    def deny_house(self, house_id: ObjectId):

        granular_house: dict = self.granular.setdefault('House', {})
        if granular_house.pop(str(house_id), None):  # извлекаем список прав
            if not isinstance(self.current, dict):
                self.current = {}

            current_house: dict = self.current.setdefault('House', {})
            allow: dict = current_house.setdefault('allow', {})

            for act in allow:  # могут быть не все из 'c','r','u','d'
                allow[act].remove(house_id)  # WARN должен существовать

    def allow_tab(self, tab_id: ObjectId,
            create=True, read=True, update=True, delete=True):

        permissions: dict = self.crud(create, read, update, delete)

        granular_tab: dict = self.granular.setdefault('Tab', {})
        if create or read or update or delete:
            granular_tab[str(tab_id)] = [{'permissions': {
                act: var for act, var in permissions.items() if var  # без False
            }, '_id': ObjectId()}]
        elif granular_tab.get(str(tab_id), False):
            del granular_tab[str(tab_id)]  # WARN удаляем элемент

        current_tab: dict = self.current.setdefault('Tab', {})
        allow: dict = current_tab.setdefault('allow', {})

        for act, var in permissions.items():  # 'c','r','u','d'
            allowed: list = allow.setdefault(act, [])
            if var and tab_id not in allowed:
                allowed.append(tab_id)
            elif not var and tab_id in allowed:
                allowed.remove(tab_id)

    def deny_tabs(self, *tab_id_s: ObjectId):

        granular_tabs: dict = self.granular.get('Tab', {})
        for tab_id in granular_tabs:
            if not tab_id_s or tab_id in tab_id_s:
                # [ {'permissions': crud(False x 4), _id: ObjectId()} ]
                granular_tabs[tab_id] = []

        current_allow: dict = self.current.get('Tab', {}).get('allow', {})
        for action in current_allow:  # 'c', 'r', 'u', 'd'
            if not tab_id_s:
                current_allow[action] = []
                continue

            current_tabs: list = current_allow[action]
            for tab_id in tab_id_s:
                if tab_id in current_tabs:
                    current_tabs.remove(tab_id)

    def clone_tabs(self, other: 'Permissions'):

        self.granular['Tab'] = other.granular.get('Tab', {})  # : dict

        self.current['Tab'] = other.current.get('Tab', {})  # : dict

    def clone_obj_tabs(self, _type: str, _id: ObjectId):

        permission_id: str = self.id_format(_type, _id)

        other: Permissions = Permissions.objects(__raw__={
            '_id': permission_id
        }).first()
        assert other is not None, f"Допуски {permission_id} не найдены"

        self.clone_tabs(other)


class ClientTab(Document):
    """
    Вкладки клиентской программы
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Tab',
    }
    slug = StringField(
        required=True,
        verbose_name='Системное имя вкладки',
        validation=_not_contain_point,
    )
    title = StringField(
        required=True,
        verbose_name='Заголовок вкладки',
    )
    title_ext = StringField(verbose_name='Расширенный заголовок вкладки')
    description = StringField(verbose_name='Описание вкладки')
    parent = ObjectIdField(default=None, verbose_name='Родительская вкладка')
    promo_url = StringField(verbose_name='промо урла')
    _type = ListField()
    _help_tips = ListField()
    permissions_help = StringField(null=True)
    departments = ListField()
    resource_binds = ListField()
    is_active = BooleanField(
        required=True,
        default=True,
        verbose_name='Флаг активности вкладки'
    )
    help = StringField(verbose_name='Интерактивная справка')

    MODULE_1C = 'module_1c'

    @classmethod
    def get_tabs_list(cls):
        return list(cls.objects.as_pymongo())

    @classmethod
    def registry(cls, titles: bool = False, inactive: bool = False,
            secured: bool = False, admin: bool = False) -> dict:
        """Перечень признаков и идентификаторов (или заголовков) вкладок"""
        types: list = ['PublicTab']
        if secured:
            types.append('SecuredTab')
        if admin:
            types.append('AdminTab')
        query: dict = {'_type': {'$in': types}}

        if inactive is False:
            query['is_active'] = True

        return {tab['slug']: tab['title'] if titles else tab['_id']
            for tab in cls.objects(__raw__=query).only(
                'slug', 'title'
            ).as_pymongo().order_by('slug')}

    # def check_children(self):
    #     if self.parent:
    #         parent_tab = ClientTab.objects(id=self.parent).first()
    #         child_tabs = ClientTab.objects(
    #             parent=self.parent
    #         ).as_pymongo().only('promo_url')
    #         has_promo_urls = any([
    #             tab.get('promo_url')
    #             for tab in child_tabs
    #         ])
    #         parent_tab.available = bool(has_promo_urls + 0)
    #         parent_tab.save()
    #
    # def save(self, *args, **kwargs):
    #     saved_tab = super().save(*args, **kwargs)
    #     self.check_children()
    #
    #     return saved_tab
