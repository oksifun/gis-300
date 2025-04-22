import datetime

from bson import ObjectId
from mongoengine import Document, ObjectIdField, DictField, DateTimeField, \
    ListField

from app.rosreestr.tasks.compraison_params import statistic_for_house_in_cache
from processing.data_producers.associated.base import get_binded_houses
from processing.models.billing.fias import Fias
from processing.models.permissions import Permissions


class FiasTreeAccountError(Exception):
    pass


class AccountFiasTree(Document):
    meta = {
        'db_alias': 'cache-db',
        'collection': 'account_fias_tree',
    }

    provider = ObjectIdField(required=True,
                             verbose_name='Ссылка на организацию')
    account = ObjectIdField(verbose_name='Ссылка на на работника')
    tree = ListField(DictField(verbose_name='Дерево ФИАСа для работника/орг.'))
    updated = DateTimeField()

    @classmethod
    def get_provider_tree_queryset(cls, provider_id):
        return cls.objects(
            __raw__={
                'provider': provider_id,
                'account': None,
            },
        )

    @classmethod
    def get_provider_tree(cls, provider_id):
        return cls.get_provider_tree_queryset(provider_id).first()

    def get_houses_and_tree(self):
        """
        Метод находит все дома организации и строит дерево,
        если передан, то дерево строится для него
        """
        houses_ids = get_binded_houses(self.provider)
        # Поиск домов работника в правах
        if self.account:
            query = dict(__raw__={'_id': 'Account:{}'.format(self.account)})
            acc_permission = Permissions.objects(**query).as_pymongo()
            # Если права найдены
            if acc_permission:
                acc_permission = acc_permission[0]
                # Поиск прав на дома
                house_permissions = acc_permission['granular'].get('House')
                if house_permissions:
                    houses = [ObjectId(key)
                              for key in house_permissions]
                    # На всякий случай проверяем, что все дома из списка
                    # разрешений работника присутсвуют у провайдера
                    houses = list(filter(lambda x: x in houses_ids, houses))
                else:
                    raise FiasTreeAccountError('В правах нет домов')
            # Если не права найдены
            else:
                raise FiasTreeAccountError('Права не найдены')
        else:
            houses = houses_ids
        self.__houses = houses
        self.build_tree(houses)

    def build_tree(self, houses_id):
        """
        Метод строит дерево ФИАСа на основании переданного списка домов
        для работника
        :param houses_id: list
        """
        if not houses_id:
            self.tree = []
            return
        # Если передан список id домов, нужно сделать запрос в коллекцию
        if isinstance(houses_id[0], ObjectId):
            from app.house.models.house import House
            houses = House.objects(
                id__in=houses_id,
            ).only(
                'id',
                'fias_street_guid',
                'short_address',
                'number',
                'bulk',
                'structure',
            ).as_pymongo()
        else:
            raise AttributeError('Houses ObjectId list needed')

        # Поиск документов ФИАСа по street_guid домов
        street_guid_list = list({x['fias_street_guid'] for x in houses})

        # упорядочивание
        def get_order(str_num):
            if str_num.isdigit():
                return str_num.zfill(5)
            else:
                return '10000{}'.format(str_num)

        houses = sorted(houses, key=lambda i: (
            get_order(i.get('number') or ''),
            get_order(i.get('bulk') or ''),
            get_order(i.get('structure') or ''),
        ))
        # Построение дерева, двигаясь из корня
        tree = {}
        # Добавление домов в каждую ветку
        for house in houses:
            branch = tree.setdefault(house['fias_street_guid'], [])
            branch.append(dict(
                _id=house['_id'],
                short_address=house['short_address']
            ))
        # Делаем ветки
        query = dict(AOGUID__in=street_guid_list)
        fias_docs = Fias.objects(**query).order_by('-LIVESTATUS').as_pymongo()
        branches = {}
        for doc in fias_docs:
            branch = branches.setdefault(doc['AOGUID'], {})
            if not branch:
                branch = branches[doc['AOGUID']]
                branch['AOGUID'] = doc['AOGUID']
                branch['name'] = '{} {}'.format(
                    doc['SHORTNAME'],
                    doc['FORMALNAME'],
                )
                branch['level'] = doc['AOLEVEL']
                branch['houses'] = tree[doc['AOGUID']]
                branch['parent'] = doc['PARENTGUID']
            else:
                # Нужно убедиться, что дома уникальны
                branch_houses = [x['_id'] for x in branch['houses']]
                extra_houses = [
                    x for x
                    in tree[doc['AOGUID']]
                    if x['_id'] not in branch_houses
                ]
                if extra_houses:
                    branch['houses'].extend(extra_houses)

        # Слияние имеющихся веток, если в результате сбора получилось,
        # что дети и родители оказались на одном уровне
        self._merge_branches(branches)

        # Рекурсивное построение дерева
        tree = self._get_next_branches(
            list({x['PARENTGUID'] for x in fias_docs if x.get('PARENTGUID')}),
            branches
        )
        # Приведение дерева к списку.
        # Если на первом уровне один элемент - убираем его
        # и вставляем наследников, добавляя названиям улиц адрес родитиля
        self.tree = self._tree_scoping(tuple(tree.values()))

    def _get_next_branches(self, parents_ids, branches):
        """Получение следующей ветки из предыдущих веток"""

        # Если нет родителей у всех веток, прекращаем рекурсию
        # Также прекращаем, если ветка на уровне осталась одна
        # if not parents_ids or len(branches) == 1:
        if not parents_ids:
            return branches
        # Временное хранилище для веток, которые уже не имеют родителей
        temp = {b: branches[b] for b in branches if not branches[b]['parent']}
        # Удаление из рабочего словаря ветки без родителей
        for branch in temp:
            branches.pop(branch)

        # Следующий уровень
        query = dict(AOGUID__in=parents_ids)
        fias_parents = Fias.objects(
            **query
        ).only(
            'id',
            'PARENTGUID',
            'AOGUID',
            'AOLEVEL',
            'SHORTNAME',
            'OFFNAME',
            'FORMALNAME',
        ).order_by(
            '-LIVESTATUS'
        ).as_pymongo()

        # Подготовим младшую ветку для отращивания корня
        child_branches = {}
        for b in branches:
            child_branch = child_branches.setdefault(
                branches[b]['parent'], []
            )
            child_branch.append(branches[b])
        # Следующая вета
        next_branches = {}
        for p_f in fias_parents:
            if not child_branches.get(p_f['AOGUID']):
                continue
            branch = next_branches.setdefault(p_f['AOGUID'], {})
            if not branch:
                branch = next_branches[p_f['AOGUID']]
                branch['AOGUID'] = p_f['AOGUID']
                branch['name'] = '{} {}'.format(p_f['SHORTNAME'],
                                                p_f['FORMALNAME'])
                branch['level'] = p_f['AOLEVEL']
                inheritors = self.smart_sort(child_branches[p_f['AOGUID']])
                branch['inheritors'] = inheritors
                branch['parent'] = p_f.get('PARENTGUID')

        # Слияние имеющихся веток, если в результате сбора получилось,
        # что дети и родители оказались на одном уровне
        self._merge_branches(next_branches)

        # Если есть временные данные, то вернем их обранто
        def _extend_inheritors(target_list, by_data):
            for source_data in by_data:
                found = False
                for target_data in target_list:
                    if target_data['AOGUID'] == source_data['AOGUID']:
                        _extend_inheritors(
                            target_data['inheritors'],
                            source_data['inheritors'],
                        )
                        found = True
                if not found:
                    target_list.append(source_data)

        if temp:
            for key in temp:
                if key in next_branches:
                    _extend_inheritors(
                        next_branches[key]['inheritors'],
                        temp[key]['inheritors'],
                    )
                else:
                    next_branches[key] = temp[key]

        return self._get_next_branches(
            [v['parent'] for v in next_branches.values() if v.get('parent')],
            next_branches
        )

    @staticmethod
    def _merge_branches(next_branches):
        """
        Слияние имеющихся веток, если в результате сбора получилось,
        что дети и родители оказались на одном уровне
        """
        trash_bin = []
        for branch in next_branches:
            cur_branch = next_branches[branch]
            for child in next_branches:
                cur_child = next_branches[child]
                if branch == cur_child['parent']:
                    c_b = cur_branch.setdefault('inheritors', [])
                    c_b.append(cur_child)
                    trash_bin.append(child)
        # Удаление объединенных детей дерева по ключам из корзины
        for key in trash_bin:
            next_branches.pop(key)

    def _tree_scoping(self, tree):
        """
        Приведение дерева к списку.
        Если на первом уровне один элемент - убираем его
        и вставляем наследников, добавляя названиям улиц адрес родитиля
        """
        while len(tree) == 1:
            # Если есть дочерние элементы
            if tree[0].get('inheritors') and not tree[0].get('houses'):
                for i in tree[0]['inheritors']:
                    i['name'] = tree[0]['name'] + ', ' + i['name']
                tree = tree[0]['inheritors']
            else:
                break
        for branch in tree:
            if branch.get('inheritors'):
                branch['inheritors'] = self._tree_scoping(branch['inheritors'])
        return tree

    def smart_sort(self, inheritors: list):
        """
        Сортирвка ветки дерева и одного его наследника по имени улицы.
        :param inheritors: та самая ветка
        :return: отсортированный список inheritors
        """
        inheritors.sort(key=lambda x: x['name'])
        for child in inheritors:
            if child.get('inheritors'):
                child['inheritors'].sort(key=lambda x: x['name'])
        return inheritors

    def save(self, *arg, **kwargs):
        self.get_houses_and_tree()
        self.updated = datetime.datetime.now()
        super().save(*arg, **kwargs)
        statistic_for_house_in_cache.delay(self.__houses)


def find_branch_by_aoguid(tree_as_dicts_list, aoguid):
    for node in tree_as_dicts_list:
        if node['AOGUID'] == aoguid:
            return node
        if not node.get('inheritors'):
            continue
        result = find_branch_by_aoguid(node['inheritors'], aoguid)
        if result:
            return result
    return None


def fill_fias_parents_by_aoguid(tree_as_dicts_list, aoguid, target_list):
    for node in tree_as_dicts_list:
        if node['AOGUID'] == aoguid:
            target_list.append(node['AOGUID'])
            return node
        if not node.get('inheritors'):
            continue
        _list = []
        result = fill_fias_parents_by_aoguid(node['inheritors'], aoguid, _list)
        if result:
            target_list.extend(_list)
            return result
    return None
