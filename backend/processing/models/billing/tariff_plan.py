from bson import ObjectId
from dateutil.relativedelta import relativedelta
from mongoengine import Document, ReferenceField, StringField, BooleanField, \
    DateTimeField, IntField, ListField, DictField, DynamicField, \
    EmbeddedDocument, ObjectIdField, FloatField, EmbeddedDocumentListField, \
    EmbeddedDocumentField
import datetime

from app.caching.models.current_tariffs_tree import TariffsFolder, \
    CurrentTariffsTree, TariffPlanShortData
from processing.models.choice.tariff import TARIFF_TYPES_CHOICES, TariffType, \
    PRIVILEGE_CALCULATION_TYPES_CHOICES, PrivilegeCalculationType, \
    TARIFF_RULES_PARENT_RELATIONS_CHOICES, \
    TARIFF_RULE_ACTION_PARAM_TYPES_CHOICES, TariffRuleActionParamType, \
    TARIFF_RULE_ACTIONS_CHOICES, TariffRuleAction, \
    TARIFFS_SUM_VALUES_SETTINGS_TYPES_CHOICES, TariffsSumValueSettingsType


class TariffNamedValue(EmbeddedDocument):
    value = IntField()
    title = StringField()


class TariffNamedFormula(EmbeddedDocument):
    value = StringField(required=True)
    value_sequence = DictField()
    title = StringField()


class TariffSettings(EmbeddedDocument):
    """
    Настройки тарифа
    """
    calc_type = StringField(
        required=True,
        choices=PRIVILEGE_CALCULATION_TYPES_CHOICES,
        default=PrivilegeCalculationType.OWN,
        verbose_name='Как считается льгота',
    )
    hide_on_empty = BooleanField(
        required=True,
        default=False,
        verbose_name='Скрывать в квитанции, если по нему ничего не начислено',
    )
    use_privileges = BooleanField(
        required=True,
        default=True,
        verbose_name='Считать льготы',
    )
    allow_pennies_calc = BooleanField(
        required=True,
        default=True,
        verbose_name='Разрешено начислять пени на долг по услуге',
    )


class TariffFormulas(EmbeddedDocument):
    """
    Формулы расчета
    """
    main = StringField(required=True)
    main_sequence = DictField()
    consumption = StringField(required=True)
    consumption_sequence = DictField()
    additional = EmbeddedDocumentListField(TariffNamedFormula)


class FormulaIf(EmbeddedDocument):
    value = StringField()
    value_sequence = DictField()


class ActionParameter(EmbeddedDocument):
    type = StringField(
        required=True,
        choices=TARIFF_RULE_ACTION_PARAM_TYPES_CHOICES,
        default=TariffRuleActionParamType.FORMULA
    )
    value = StringField()
    value_sequence = DictField()


class RuleAction(EmbeddedDocument):
    action = StringField(
        required=True,
        choices=TARIFF_RULE_ACTIONS_CHOICES,
        default=TariffRuleAction.TARIFF,
    )
    action_params = EmbeddedDocumentListField(ActionParameter)


class PrecalculationRule(EmbeddedDocument):
    """
    Условие тарифа
    """
    id = ObjectIdField(db_field='_id')
    formula_if = EmbeddedDocumentListField(
        FormulaIf,
        verbose_name='Формула проверки выполнения условия',
    )
    actions = EmbeddedDocumentListField(
        RuleAction,
        verbose_name='Действия при выполнении условия',
    )
    parent_ix = IntField(default=None, verbose_name='Головное условие')
    parent_relation = StringField(
        choices=TARIFF_RULES_PARENT_RELATIONS_CHOICES,
    )
    comment = StringField(verbose_name='Обоснование или описание условия')

    # TODO: удалить поле
    rule_sector = DynamicField()


class TariffEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id', required=True, default=ObjectId)
    ix = IntField(required=True, verbose_name='Порядок сортировки тарифа')
    norm = FloatField(
        required=True,
        default=0.0,
        verbose_name='Значение норматива',
    )
    type = StringField(
        required=True,
        choices=TARIFF_TYPES_CHOICES,
        default=TariffType.URBAN,
        verbose_name='Тип тарифа',
    )
    foreign_name = StringField(
        required=False,
        verbose_name="Заголовок на иностранном языке"
    )
    group = IntField(
        default=0,
        required=True,
        verbose_name='Вхождение в группу',
    )
    value = IntField(required=True, default=0, verbose_name='Значение тарифа')
    units = StringField(
        null=True,
        verbose_name='Единицы измерения')
    title = StringField(required=True, verbose_name='Заголовок')
    rules = EmbeddedDocumentListField(
        PrecalculationRule,
        verbose_name='Условия',
    )
    settings = EmbeddedDocumentField(
        TariffSettings,
        verbose_name='Настройки тарифа',
    )
    formulas = EmbeddedDocumentField(
        TariffFormulas,
        verbose_name='Формулы тарифа',
    )
    reasoning = StringField(verbose_name='Обоснование тарифа')
    add_values = EmbeddedDocumentListField(
        TariffNamedValue,
        verbose_name='Дополнительные значения',
    )
    description = StringField(verbose_name='Описание')
    service_type = ObjectIdField(
        required=True,
        verbose_name='Признак платежа с его кодом',
    )
    allow_pennies = BooleanField(required=True, default=True)


class GlobalValueEmbedded(EmbeddedDocument):
    """
    Формулы расчёта глобальных переменных тарифного плана
    """
    id = ObjectIdField(db_field='_id')
    title = StringField(required=True)
    description = StringField()
    formula = StringField(required=True)
    formula_sequence = DictField()
    rules = EmbeddedDocumentListField(PrecalculationRule)


class SumValueEmbedded(EmbeddedDocument):
    """
    Формулы суммирования
    """
    id = ObjectIdField(db_field='_id')
    title = StringField(required=True)
    description = StringField()
    service_type = ObjectIdField(required=True)
    type = StringField(
        required=True,
        choices=TARIFFS_SUM_VALUES_SETTINGS_TYPES_CHOICES,
        default=TariffsSumValueSettingsType.REGIONAL
    )
    formula_code = StringField(
        verbose_name='Код, для использования в формулах, а также для указания '
                     'соответствия региональной настройке',
    )
    formula = StringField(required=True)
    formula_sequence = DictField()
    rules = EmbeddedDocumentListField(PrecalculationRule)


class TariffPlan(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'TariffPlan',
    }

    # legacy - Required(Ref('TariffPlanGroup')
    group = ReferenceField(
        'self',
        default=None,
        verbose_name="Входит в группу ТП"
    )

    title = StringField(required=True, verbose_name="Заголовок")
    provider = ObjectIdField(
        required=False,
        verbose_name="Организация-владелец (для системных ТП отсутствует)",
    )

    description = StringField(verbose_name="Описание")
    is_system = BooleanField(
        required=True,
        default=False,
        verbose_name="системный, бывший по зао-отдел",
    )

    # legacy - Required(Date, default=datetime.date.today)
    date_from = DateTimeField(
        required=True,
        default=datetime.date.today,
        verbose_name="Дата начала действия ТП",
    )
    date_till = DateTimeField(
        default=None,
        verbose_name="Дата окончания действия ТП",
    )
    created = DateTimeField(required=True, default=datetime.datetime.now,
                            verbose_name="Дата создания")

    # legacy - Required(RegionCode, default=78)
    region_code = IntField(
        min_value=1,
        max_value=200,
        default=78,
        verbose_name="Код региона",
    )

    # TODO: define as embedded
    # legacy - [Tariff]
    tariffs = EmbeddedDocumentListField(
        TariffEmbedded,
        verbose_name="Список тарифов",
    )
    global_values = EmbeddedDocumentListField(
        GlobalValueEmbedded,
        verbose_name="Список глобальных переменных",
    )
    sum_values = EmbeddedDocumentListField(
        SumValueEmbedded,
        verbose_name="Список суммирований",
    )
    _type = ListField(StringField(), verbose_name='Системный тип')
    auxiliary = BooleanField(
        verbose_name='Является ли служебным (виден всегда)',
    )

    def update_regional_settings(self):
        from processing.models.billing.regional_settings import RegionalSettings

        r_settings = \
            RegionalSettings.objects(region_code=self.region_code).get()
        for ix, t_plan in enumerate(r_settings.tariff_plans):
            if t_plan.id == self.pk:
                short_data = TariffPlanShortData.from_tariff_plan(self)
                r_settings.tariff_plans[ix] = short_data
                r_settings.save()
                break


class TariffsTree(Document):
    """
    Схема дерева:

    -ид папки
    -наименование
    -список ид тарифных планов
    -вложенный список папок
    -дата изменения

    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'TariffsTree',
    }

    provider = ReferenceField(
        'processing.models.billing.provider.Provider',
        required=True,
        verbose_name='Организация-владелец'
    )
    cache_updated = DateTimeField()
    tree = DynamicField()

    def create_root(self):
        if self.tree:
            return self.tree[0]
        self.tree.append({
            '_id': ObjectId(),
            'title': '.',
            'updated': datetime.datetime.now(),
            'tariff_plans': [],
            'sub_folders': [
                {
                    '_id': ObjectId(),
                    'title': 'Служебные',
                    'updated': datetime.datetime.now(),
                    'tariff_plans': [],
                },
                {
                    '_id': ObjectId(),
                    'title': 'Архив',
                    'updated': datetime.datetime.now(),
                    'tariff_plans': [],
                },
            ],
        })
        return self.tree[0]

    def update_cache(self, forced=False):
        """
        Обновляет кэш организации:
        current_tariffs_tree - текущее дерево
        tariffs_folder - кэш папок
        """
        self._update_folders_cache(forced=forced)
        self._update_current_tree_cache()
        self.cache_updated = datetime.datetime.now()
        self.save()

    def pop_object_from(self, object_id, folder_from):
        found = self.find_folder_by_id(folder_from)
        if found:
            # если это тарифный план
            if object_id in found['tariff_plans']:
                found['updated'] = datetime.datetime.now()
                found['tariff_plans'].remove(object_id)
                return object_id
            # если этот папка
            for ix, subfolder in enumerate(found['sub_folders']):
                if object_id == subfolder['_id']:
                    found['updated'] = datetime.datetime.now()
                    found['sub_folders'].pop(ix)
                    return subfolder
        return None

    def put_object_to(self, object_ins, folder_to):
        found = self.find_folder_by_id(folder_to)
        if found:
            # если это тарифный план
            if isinstance(object_ins, ObjectId):
                found['updated'] = datetime.datetime.now()
                found['tariff_plans'].append(object_ins)
                return found
            # если этот папка
            if isinstance(object_ins, dict):
                object_ins['updated'] = datetime.datetime.now()
                found['updated'] = datetime.datetime.now()
                found['sub_folders'].append(object_ins)
                return found
        return None

    def find_folder_by_id(self, folder_id):

        def find_folder(target_id, folder):
            if folder['_id'] == target_id:
                return folder
            # ищем во вложенных папках
            for subfolder in folder['sub_folders']:
                if find_folder(target_id, subfolder):
                    return subfolder
            return None

        return find_folder(folder_id, self.tree[0])

    def _get_tariffs(self, ids):
        t_plans = TariffPlan.objects.as_pymongo().filter(
            id__in=ids
        ).only(
            'id',
            'title',
            'date_from',
            'created',
            'tariffs._id',
            'tariffs.title',
            'tariffs.service_type',
            'tariffs.value',
            'tariffs.description',
            'tariffs.group',
            'global_values.id',
            'sum_values.id',
        )
        for t_plan in t_plans:
            if t_plan.get('global_values'):
                t_plan['global_values'] = True
            if t_plan.get('sum_values'):
                t_plan['sum_values'] = True
            groups = {}
            for t in t_plan['tariffs']:
                g = groups.setdefault(t.pop('group'), [])
                g.append(t)
            t_plan['tariffs'] = sorted(
                [{'group': k, 'tariffs': v} for k, v in groups.items()],
                key=lambda i: i['group']
            )
        return list(t_plans)

    def _get_max_tariffs_date(self):
        t_plan = TariffPlan.objects.as_pymongo().filter(
            provider=self.provider.id
        ).only('created').order_by('-id')[0: 1]
        if t_plan:
            return t_plan[0]['created']
        return None

    def _update_folders_cache(self, forced=False):

        from processing.models.billing.provider.main import Provider
        p = Provider.objects.get(pk=self.provider.id)

        def update_node(node):
            if forced or node['updated'] > self.cache_updated:
                t_plans = self._get_tariffs(node['tariff_plans'])
                TariffsFolder.objects(folder_id=node['_id']).upsert_one(
                    provider=p,
                    folder_id=node['_id'],
                    title=node['title'],
                    sub_folders=[f['_id'] for f in node['sub_folders']],
                    tariff_plans=t_plans,
                    updated=datetime.datetime.now(),
                )
            for sub_node in node['sub_folders']:
                update_node(sub_node)

        for root_node in self.tree:
            update_node(root_node)

    def _update_current_tree_cache(self):
        max_date = self._get_max_tariffs_date()
        control_date = max_date - relativedelta(months=2)

        def get_node(data):
            subnodes = []
            has_arc = False
            for folder in sorted(data['sub_folders'],
                                 key=lambda i: i['title'].lower()):
                subnodes.append(get_node(folder))
            t_plans = self._get_tariffs(data['tariff_plans'])
            if t_plans:
                for t_plan in sorted(t_plans, key=lambda i: i['title'].lower()):
                    if (
                        t_plan['created'] >= control_date or
                        t_plan.get('auxiliary')
                    ):
                        subnodes.append(t_plan)
                    else:
                        has_arc = True
            return {
                'title': data['title'],
                'id': data['_id'],
                'nodes': subnodes,
                'has_arc': has_arc
            }

        current_tree = [get_node(self.tree[0])]
        current_tree = CurrentTariffsTree.objects(
            provider=self.provider.id
        ).upsert_one(tree=current_tree)
        return current_tree

