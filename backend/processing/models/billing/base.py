from bson import ObjectId

from mongoengine import Q, EmbeddedDocumentField, EmbeddedDocument, \
    ListField, ObjectIdField, StringField, DoesNotExist, BooleanField, \
    ValidationError


class BaseBind(EmbeddedDocument):
    REQUIRED_BINDS = tuple()
    pass


class ProviderBinds(EmbeddedDocument):
    pr = ListField(ObjectIdField())
    REQUIRED_BINDS = ('pr',)


class HouseGroupBinds(EmbeddedDocument):
    hg = ListField(ObjectIdField())
    fi = StringField(verbose_name='Привязка к ФИАС')
    REQUIRED_BINDS = ('hg',)


class ProviderHouseGroupBinds(EmbeddedDocument):
    pr = ListField(ObjectIdField())
    hg = ListField(ObjectIdField())
    REQUIRED_BINDS = ('pr', 'hg',)


class ProviderAccountBinds(EmbeddedDocument):
    pr = ListField(ObjectIdField())
    ac = ListField(ObjectIdField())
    REQUIRED_BINDS = ('pr', 'ac',)


class ProviderPositionBinds(EmbeddedDocument):
    pr = ListField(ObjectIdField())
    po = ListField(StringField())
    REQUIRED_BINDS = ('pr',)


class ProviderFiasAccountBinds(EmbeddedDocument):
    pr = ListField(ObjectIdField())
    fi = ListField(StringField())
    po = ListField(StringField())
    REQUIRED_BINDS = ('pr',)


class BindsPermissions(EmbeddedDocument):
    pr = ObjectIdField(verbose_name='Привязка к организаци')
    hg = ObjectIdField(verbose_name='Привязка к группе домов')
    dt = ObjectIdField(verbose_name='Привязка к подразделению')
    fi = StringField(verbose_name='Привязка к ФИАС')
    ac = ObjectIdField(verbose_name='Привязка к аккаунту')
    po = StringField(verbose_name='Привязка к должности')

    @property
    def serialized_binds(self):
        return {k: str(v) for k, v in self.to_mongo().items()}


class ModelMixin:
    @classmethod
    def get_binds_query(cls, binds_permissions, raw: bool = False):
        return None

    def _is_key_dirty(self, field_name: str):
        """
        Проверка, является ли поле измененным
        (только для существующего документа).
        Поле также считается измененным, если изменилось его вложенное поле.
        """

        changed_fields = (
            x for x in getattr(self, '_get_changed_fields')()
            if (
                    field_name == x
                    or f'.{field_name}.' in x
                    or x.endswith(f'.{field_name}')
                    or x.startswith(f'{field_name}.')
            )
        )
        if not getattr(self, '_created') and next(changed_fields, False):
            return True
        else:
            return False

    def _is_triggers(self, field_names: list):
        """
        Проверяет что модель только что создана
        или изменены "поля-раздражители"
        """

        # Только создали модель
        if getattr(self, '_created'):
            return True
        # Одно из полей-раздражителей изменено
        triggered_list = []
        for field in field_names:
            if self._is_key_dirty(field):
                triggered_list.append(field)
        if triggered_list:
            return triggered_list
        # Документ уже существует и поля не менялись
        return False


class ForeignDenormalizeModelMixin(ModelMixin):
    _FOREIGN_DENORMALIZE_FIELDS = []

    def _get_fields_for_foreign_denormalize(self):
        if self._created:
            return []
        else:
            return self._is_triggers(self._FOREIGN_DENORMALIZE_FIELDS)

    def _foreign_denormalize(self, denormalize_fields):
        from app.caching.tasks.denormalization import foreign_denormalize_data
        for field in denormalize_fields:
            foreign_denormalize_data.delay(
                model_from=self.__class__,
                field_name=field,
                object_id=self.pk,
            )

    def _run_denormalize_tasks(self, denormalize_tasks):
        from app.caching.tasks.denormalization import foreign_denormalize_data
        for task in denormalize_tasks:
            foreign_denormalize_data.delay(
                model_from=self.__class__,
                field_name=task.field_name,
                object_id=task.obj_id,
                task_id=task.id,
            )

    def _create_denormalize_tasks(self, field_names):
        from app.caching.models.denormalization import DenormalizationTask
        result = []
        for field_name in field_names:
            result.append(
                DenormalizationTask.create_simple_task(
                    model_name=self.__class__.__name__,
                    field_name=field_name,
                    obj_id=self.id,
                ),
            )
        return result


class BindedModelMixin(ModelMixin):

    _binds = EmbeddedDocumentField(BaseBind)

    @classmethod
    def get_binds_query(cls, binds_permissions, raw: bool = False):
        """
        Метод для преобразования переданной привязки в нужный для модели вид
        :param raw: если нужен в виде словаря
        :param binds_permissions: переданные привязки
        :return: dict, Q
        """
        if not binds_permissions:
            if raw:
                return {}
            else:
                return Q()
        result = {}
        if not isinstance(binds_permissions, dict):
            binds_permissions = binds_permissions.to_mongo()
        for name, bind in cls._binds.document_type_obj._fields.items():
            permission = binds_permissions.get(name)
            if permission:
                result[name] = permission
            elif name in cls._binds.document_type_obj.REQUIRED_BINDS:
                raise DoesNotExist('Nothing to find, no required binds')
        if raw:
            return {'_binds.' + k: v for k, v in result.items()}
        else:
            return Q(**{'_binds__' + k: v for k, v in result.items()})

    def restrict_changes(self):
        """
        Запрет на изменение поля _binds на уровне модели
        :return: Вызывает ошибку, если _binds меняются не при создании документа
        """
        restrict_condition = (
                not getattr(self, '_created')
                and '_binds' in getattr(self, '_changed_fields')
        )
        if restrict_condition:
            raise ValidationError("У Вас нет на это власти!")

    @classmethod
    def process_provider_binds(cls, provider_id, **kwargs):
        pulled = cls.objects(
            provider__ne=provider_id,
            _binds__pr=provider_id,
        ).update(pull___binds__pr=provider_id)
        pushed = cls.objects(
            provider=provider_id,
        ).update(add_to_set___binds__pr=provider_id)
        return pushed, pulled

    def save(self, *args, **kwargs):
        if not self._binds:
            binds = getattr(self, '_fields')['_binds'].document_type._class_name
            if binds == ProviderBinds.__name__:
                self._binds = ProviderBinds(pr=self._get_providers_binds())
            elif binds == ProviderHouseGroupBinds.__name__:
                self._binds = ProviderHouseGroupBinds(
                    pr=self._get_providers_binds(),
                    hg=self._get_house_binds(),
                )
        return getattr(super(), 'save')(*args, **kwargs)

    def _get_providers_binds(self):
        if hasattr(self, 'provider'):
            if isinstance(self.provider, ObjectId):
                return [self.provider]
            else:
                return [self.provider.id]
        if hasattr(self, 'owner'):
            if isinstance(self.owner, ObjectId):
                return [self.owner]
            else:
                return [self.owner.id]
        return []

    def _get_house_binds(self):
        from processing.models.billing.common_methods import get_house_groups

        house_id = getattr(getattr(self, 'house', None), 'id', None)
        return (
            get_house_groups(house_id)
            if house_id
            else []
        )

    @property
    def house_groups(self) -> list:
        """Привязки к группам домов (hg)"""
        if not self._binds:
            self._binds = HouseGroupBinds()  # по умолчанию hg=[]
        return self._binds.hg  # fi не проверяется

    @property
    def provider_binds(self) -> list:
        """Привязки к провайдерам (pr)"""
        if not self._binds:
            self._binds = ProviderBinds()  # default pr=[]
        return self._binds.pr


class RelationsProviderBindsProcessingMixin:
    def _extract_owner_id(self):
        if hasattr(self, 'owner'):
            return self.owner
        if hasattr(self, 'provider'):
            return self.provider
        if hasattr(self, 'doc') and hasattr(self.doc, 'provider'):
            return self.doc.provider.id
        return None

    def _get_providers_binds(self):
        from processing.models.billing.provider.main import ProviderRelations
        # Организации, которые будут также иметь доступ к документам
        provider_id = self._extract_owner_id()
        relations = ProviderRelations.objects(
            provider=provider_id,
        ).only(
            'slaves',
        ).as_pymongo().first()
        if not relations:
            return [provider_id]
        if hasattr(self, 'account') and self.account:
            house_id = self.account.area.house.id
        elif hasattr(self, 'house') and self.house:
            house_id = self.house
        else:
            house_id = None
        if house_id and relations.get('slaves'):
            return (
                [
                    x['provider']
                    for x in relations['slaves'] if house_id in x['houses']
                ]
                + [provider_id]
            )
        elif hasattr(self, 'account') and relations.get('slaves'):
            return (
                [
                    x['provider']
                    for x in relations['slaves']
                ]
                + [provider_id]
            )
        else:
            return [provider_id]

    @classmethod
    def _extract_owner_field(cls):
        field_names = cls._fields.keys()
        for name in ('owner', 'provider'):
            if name in field_names:
                return name
        if 'doc' in field_names:
            if (
                    isinstance(cls._fields['doc'], EmbeddedDocumentField)
                    and hasattr(cls._fields['doc'].document_type, 'provider')
            ):
                return 'doc__provider'
        return None

    @classmethod
    def process_provider_binds(cls, provider_id, force=False):
        from processing.models.billing.provider.main import ProviderRelations

        pushed = 0
        pulled = 0
        # кто разрешил смотреть свои документы
        relations = ProviderRelations.objects(
            slaves__provider=provider_id,
        ).as_pymongo()
        masters_houses = []
        for r in relations:
            for s in r['slaves']:
                if s['provider'] == provider_id:
                    masters_houses.append((r['provider'], s['houses']))
        # удалиться из чужих документов
        owner_field = cls._extract_owner_field()
        masters_providers = [p[0] for p in masters_houses]
        res = cls.objects(
            **{
                f'{owner_field}__nin': masters_providers + [provider_id],
                '_binds__pr': provider_id,
            },
        ).update(
            pull___binds__pr=provider_id,
            full_result=True,
        )
        pulled += res.modified_count
        # добавиться в свои документы
        res = cls.objects(
            **{
                owner_field: provider_id,
            },
        ).update(
            add_to_set___binds__pr=provider_id,
            full_result=True,
        )
        pushed += res.modified_count
        # добавиться в чужие разрешённые документы
        if 'account' in cls._fields or 'house' in cls._fields:
            for master_houses in masters_houses:
                s_pushed, s_pulled = cls._process_provider_master_houses_binds(
                    owner_field=owner_field,
                    master_id=master_houses[0],
                    slave_id=provider_id,
                    houses=master_houses[1],
                    force=force,
                )
                pushed += s_pushed
                pulled += s_pulled
        else:
            for master_houses in masters_houses:
                cls._process_provider_master_binds(
                    owner_field=owner_field,
                    master_id=master_houses[0],
                    slave_id=provider_id,
                )
        return pushed, pulled

    _HOUSE_FIELD_PATH = 'account.area.house._id'
    _HOUSE_FIELD_FILTER_NAME = 'account__area__house__id'

    @classmethod
    def _process_provider_master_houses_binds(cls, owner_field, master_id,
                                              slave_id, houses, force=False):
        pushed = 0
        pulled = 0
        # выясним, в какие дома надо добавить, а из каких удалить
        houses_all = cls.objects(
            **{
                owner_field: master_id,
                '_binds__pr': slave_id,
            },
        ).distinct(
            cls._HOUSE_FIELD_PATH,
        )
        if force:
            houses_allow = houses
        else:
            houses_allow = list(set(houses) - set(houses_all))
        houses_disallow = list(set(houses_all) - set(houses))
        # удалиться из запрещённых домов
        for h in houses_disallow:
            res = cls.objects(
                **{
                    owner_field: master_id,
                    '_binds__pr': slave_id,
                    cls._HOUSE_FIELD_FILTER_NAME: h,
                },
            ).update(
                pull___binds__pr=slave_id,
                full_result=True,
            )
            pulled += res.modified_count
        # добавиться в разрешённые дома
        for h in houses_allow:
            res = cls.objects(
                **{
                    owner_field: master_id,
                    cls._HOUSE_FIELD_FILTER_NAME: h,
                },
            ).update(
                add_to_set___binds__pr=slave_id,
                full_result=True,
            )
            pushed += res.modified_count
        return pushed, pulled

    @classmethod
    def _process_provider_master_binds(cls, owner_field, master_id, slave_id):
        pushed = 0
        pulled = 0
        # добавиться в разрешённые дома
        res = cls.objects(
            **{
                owner_field: master_id,
            },
        ).update(
            add_to_set___binds__pr=slave_id,
            full_result=True,
        )
        pushed += res.modified_count
        return pushed, pulled


class ChangeBlockingMixin:
    """
     Миксин, призванный проверять блокировку документа
     и недопускать изменения/удаление/обновление, если она существует.
     Класс связан с работой онлайн касс и фискализацией чеков.
     """

    lock = BooleanField(verbose_name='Стоит ли блокировка')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = self.lock

    def check_change_permissions(self):
        if self._lock is True:
            raise ValidationError("Have no permissions to change the document.")


class CustomQueryMixin:

    @classmethod
    def find(cls, *args, **kwargs):
        """
        Метод запроса через objects(), автоматически подставляющий в фильтр
        _type равный названию класса и is_deleted__ne=True,
        если эти поля не переданы в простом виде.
        """
        fields = getattr(cls, '_db_field_map')
        if not kwargs.get('_type') and '_type' in fields:
            kwargs.update(_type=cls.__name__)
        if not kwargs.get('is_deleted') and 'is_deleted' in fields:
            kwargs.update(is_deleted__ne=True)

        return getattr(cls, 'objects')(*args, **kwargs)

    @classmethod
    def find_by_binds(cls, binds, *args, **kwargs):
        fields = getattr(cls, '_db_field_map')
        if not kwargs.get('is_deleted') and 'is_deleted' in fields:
            kwargs.update(is_deleted__ne=True)
        try:
            binds_query = getattr(cls, 'get_binds_query')(binds)
        except AttributeError:
            raise AttributeError(f"{cls.__name__} has not _binds.")

        return getattr(cls, 'objects')(binds_query, *args, **kwargs)


class FilesDeletionMixin(ModelMixin):
    """
    Миксин для удаления файлов из GridFS (модель Files)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.relevant_file_fields = self.find_file_fields()

    def save(self, *args, **kwargs):
        # self.check_file_fields()
        return getattr(super(), 'save')(*args, **kwargs)

    def delete(self, signal_kwargs=None, **write_concern):
        # self.check_file_fields(delete_mode=True)
        return getattr(super(), 'delete')(signal_kwargs, **write_concern)

    def check_file_fields(self, delete_mode=False):
        """
        Поиск всех полей, у которых модель Files.
        Проверка на наличие изменений и удаление соответсвующих
        файлов из GridFS.
        Учитывает безопасное удаление документов (is_deleted=True)
        :param delete_mode: Если True, то не будет проверок изменения полей
        :return количество удаленных файлов
        """
        # Если модель только что создали, ничег оне проверяем
        if getattr(self, '_created'):
            return 0

        # Список словарей - имеющихся файлов с их путями в модели и ID в GridFS
        relevant_file_fields = getattr(self, 'relevant_file_fields', None)
        if relevant_file_fields is None:
            raise NotImplementedError(
                'Атрибут relevant_file_fields '
                'не определен при инициализации модели!'
            )

        # Если в модели используется безопасное удаление, то учтем это
        delete_mode = delete_mode or getattr(self, 'is_deleted', False)
        # Получим только те поля, которые относятся в фалам.
        # Так мы исключим лишние проверки и возможность ошибки, когда изменили
        # имя файла, но его не перезатирали
        changed_fields = {
            x for x in getattr(self, '_get_changed_fields')()
            if x.endswith('.uuid') or x.endswith('.file')
        }
        deleted = 0
        for field in relevant_file_fields:
            # Проверяем вхождение пути до файла в измененных файловых полях
            field_is_changed = next(
                (x for x in changed_fields if field['path'] in x), False
            )
            if delete_mode or field_is_changed:
                from lib.gridfs import delete_file_in_gridfs
                try:
                    delete_file_in_gridfs(
                        file_id=field['file'],
                        uuid=field['uuid']
                    )
                    deleted += 1
                except DoesNotExist:
                    pass
        return deleted

    def find_file_fields(self, model=None, fields=[], path=None):
        """
        Рекурсивный поиск всех полей, у которых есть модель Files.
        :return словарь с путямя к файлам модели и их файл ID
        """
        path = path or ''
        # Обработаем ситуации, когда передана какая-то ерудна,
        # типа список цифр или строк
        try:
            model = model if model is not None else self
            db_ref_fields = self._guess_db_ref_fields(model)
            model = {x: model[x] for x in model if x not in db_ref_fields}
        except TypeError:
            return

        from processing.models.billing.files import Files

        for name, field in model.items():
            # Добавляем поле к списку, содержащее путь к полю и file_id
            if isinstance(field, Files):
                # Если есть хотя бы какой-то идентификатор, добавим
                if field.file or getattr(field, 'uuid', None):
                    data = dict(
                        file=field.file,
                        # TODO Удалить uuid, когда файлы в модели
                        #  будут содержать только file и name
                        uuid=getattr(field, 'uuid', None),
                        path=f'{path}.{name}'.lstrip('.')
                    )
                    fields.append(data)
            # Если поле вложенное, то проверим его поля
            elif hasattr(field, '_fields') and not field._is_document:
                self.find_file_fields(field, fields, f'{path}.{name}')

            elif isinstance(field, list):
                for num, list_field in enumerate(field):
                    new_path = f'{path}.{name}.{num}'
                    self.find_file_fields(list_field, fields, new_path)
        return fields

    def _guess_db_ref_fields(self, model_dict):
        if not hasattr(model_dict, 'to_mongo'):
            return set()

        return {
            k for k, v in dict(model_dict.to_mongo()).items()
            if isinstance(v, list) and v and isinstance(v[-1], ObjectId)
        }
