import json
from bson import ObjectId

from app.legal_entity.models.legal_entity import LegalEntity
from app.legal_entity.models.legal_entity_contract import LegalEntityContract
from app.legal_entity.models.legal_entity_service import EntityAgreementService
from processing.data_producers.associated.services import get_service_names
from processing.data_producers.balance.services.base import ServicesBalanceBase, \
    _PENALTY_SERVICE_TYPES_CHANGE
from processing.data_producers.balance.services.vendors import \
    VendorsServicesBalance
from processing.models.billing.account import Tenant
from processing.models.billing.accrual import Accrual
from app.accruals.models.accrual_document import AccrualDoc
from processing.accounting.export.exceptions import TenantWithoutInnError
from processing.accounting.export.abstract import JSONFileCreator
from processing.accounting.export.zip_file import ZipArchive
from app.house.models.house import House
from processing.models.permissions import Permissions

PENALTY_SERVICE_TYPES_CHANGE = {*_PENALTY_SERVICE_TYPES_CHANGE, 'penalties'}


class ExportSummaryServicesBalance(ServicesBalanceBase):
    def __init__(
            self,
            binds=None,
            sectors=None,
            by_bank=True,
            accounts_list=None,
            accounts_type=None,
            area_type=None,
            houses=None
    ):
        super().__init__(
            binds=binds,
            sectors=sectors,
            by_bank=by_bank,
        )

        self.accounts_list = accounts_list
        self.accounts_type = accounts_type
        self.area_type = area_type
        self.houses = houses

    def _get_custom_accruals_filter(self):
        query = {
            'account.area.house._id': {'$in': self.houses},
        }

        if self.area_type:
            query.update({'account.area._type': self.area_type})
        if self.accounts_list:
            query.update({'account._id': {'$in': self.accounts_list}})
        elif self.accounts_type:
            query.update({'account._type': self.accounts_type})
        return query

    def _get_custom_offsets_filter(self):
        query = {
            'refer.account.area.house._id': {'$in': self.houses},
        }

        if self.area_type:
            query.update({'refer.account.area._type': self.area_type})
        if self.accounts_list:
            query.update({'refer.account._id': {'$in': self.accounts_list}})
        elif self.accounts_type:
            query.update({'refer.account._type': self.accounts_type})
        return query

    def _get_custom_payments_filter(self):
        query = {
            'account.area.house._id': {'$in': self.houses},
        }

        if self.area_type:
            query.update({'account.area._type': self.area_type})
        if self.accounts_list:
            query.update({'account._id': {'$in': self.accounts_list}})
        elif self.accounts_type:
            query.update({'account._type': self.accounts_type})
        return query


AREA_TYPES = ['LivingArea',
              'NotLivingArea',
              'ParkingArea']

OUTPUT_AREA_TYPES = {
    'LivingArea': 'living_area',
    'NotLivingArea': 'not_living_area',
    'ParkingArea': 'parking_area',
}


class ExportSummary:
    def __init__(
            self,
            houses,
            accrual_docs,
            date_from,
            date_till,
            provider_id,
            binds=None,
    ):
        self.files = []
        self.houses = houses
        self.accrual_docs = accrual_docs
        self.date_from = date_from
        self.date_till = date_till
        self.provider_id = provider_id
        self.binds = binds
        self.old_method = False

    def distinct_legal_tenants(self) -> dict:
        error_legal_tenants = list()
        legal_groups = dict()
        legal_tenants = Tenant.objects(
            _type='LegalTenant',
            area__house__id__in=self.houses,
            is_deleted__ne=True
        ).only('id', 'inn', 'str_name', 'area')
        for tenant in legal_tenants:
            if not tenant.inn:
                error_legal_tenants.append(
                    {
                        'id': str(tenant.id),
                        'name': tenant.str_name,
                        'address': tenant.area.house.address
                    })
                continue
            group = legal_groups.setdefault(tenant.inn, [])
            group.append(tenant.id)
        if error_legal_tenants:
            raise TenantWithoutInnError(
                json.dumps({
                    'text': 'Выгрузка невозможна, так как у следующих '
                            'юридических лиц не найден обязательный реквизит: '
                            'ИНН',
                    'tenants': error_legal_tenants
                })
            )
        return legal_groups

    def _is_old_method(self):
        new_method_tab_id = "61499b8b7d350e002d5a1db6"
        provider_permissions = Permissions.objects(
            actor_id=self.provider_id
        ).as_pymongo().get()
        permission = provider_permissions['granular']['Tab'].get(
            new_method_tab_id
        )
        if permission:
            return permission[0]['permissions'].get('r')
        return True

    def _provider_uses_vendors(self):
        vendor_service = EntityAgreementService.objects(
            provider=self.provider_id
        )
        return bool(vendor_service)

    def format_credit_data(self, raw_data, tariff_plans):
        services_ids = {x for x in raw_data}
        services_names = get_service_names(
            self.provider_id,
            list(services_ids),
            tariff_plans,
        )
        advance = raw_data.pop('advance', None)
        penalties = raw_data.pop('penalties', {})
        penalties = {
            'paid': penalties.get('payment', 0) / 100,
            'service_id': 'penalties',
            'service_name': 'Пени',
        }
        data = dict()
        data['penalties'] = penalties
        data['services'] = list()

        for s_id, summary in raw_data.items():
            if not summary['payment']:
                continue
            title = services_names.get(
                s_id, {}
            ).get(
                'title', ''
            )
            service = {
                'service_name': title,
                'service_id': str(s_id),
                'paid': summary['payment'] / 100
            }
            data['services'].append(service)

        return data

    def __get_legal_entity_meta(self, entity):
        meta = dict()
        if isinstance(entity, ObjectId):
            entity = LegalEntity.objects.get(pk=entity)
        contract = LegalEntityContract.get_or_create(
            entity,
            self.provider_id
        )
        meta['type'] = 'Юридические лица'
        meta['contragent_name'] = entity.current_details.current_name
        meta['contragent_inn'] = entity.current_details.current_inn
        meta['contract_name'] = contract.name
        meta['contract_date'] = contract.date.isoformat() if contract.date \
                                                          else ''
        return meta

    def _get_credit_file_meta(self, house_id, agent):
        header = dict(file_type='Расщепление')

        house = House.objects.get(pk=house_id)
        header['house_id'] = str(house.id)
        header['house_address'] = house.address or ''

        if agent['accounts_type'] == 'PrivateTenant':
            header['type'] = 'Физические лица'
        elif agent['accounts_type'] == 'LegalTenant':
            account_id = agent['accounts_list'][0]
            account = Tenant.objects.get(pk=account_id)
            entity = account.try_create_legal_entity()
            header.update(self.__get_legal_entity_meta(entity))
        return header

    def _get_debit_match(self):
        match = {
            'doc._id': {'$in': [ad.id for ad in self.accrual_docs]}
        }
        return match

    def _get_penalties_pipeline(self):
        match = self._get_debit_match()
        match.update({'totals.penalties': {'$ne': 0}})
        pipeline = [
            {'$match': match},
            {'$project': {
                'penalties': '$totals.penalties',
                'account': '$account._id',
                'accrual_doc': '$doc._id',
            }},
            {'$lookup': {
                'from': 'Account',
                'localField': 'account',
                'foreignField': '_id',
                'as': 'account',
            }},
            {'$unwind': '$account'},
            {'$project': {
                'account_type': {'$arrayElemAt': ['$account._type', 0]},
                'area_type': {'$cond': [
                    {'$lte': [{'$size': '$account.area._type'}, 2]},
                    {'$arrayElemAt': ['$account.area._type', 0]},
                    {'$arrayElemAt': ['$account.area._type', -2]},
                ]},
                # 'entity': '$account.entity',
                'entity': {'$cond': {
                    'if': {'$eq': ['$account.entity', None]},
                    'then': '$$REMOVE',
                    'else': '$account.entity',
                }},
                'accrual_doc': 1,
                'penalties': 1,
            }},
            {'$group': {
                '_id': {
                    'accrual_doc': '$accrual_doc',
                    'account_type': '$account_type',
                    'entity': '$entity',
                    'area_type': '$area_type'
                },
                'penalties': {'$sum': '$penalties'},
            }},
            {'$group': {
                '_id': {
                    'accrual_doc': '$_id.accrual_doc',
                    'account_type': '$_id.account_type',
                    'entity': '$_id.entity',
                },
                'services': {'$addToSet': {
                    'area_type': '$_id.area_type',
                    'total': '$penalties',
                    'service_id': 'penalties'
                }}
            }}
        ]
        return pipeline

    def _get_debit_pipeline(self):
        pipeline = [
            {'$match': self._get_debit_match()},
            {'$project': {
                'services': 1,
                'value': 1,
                'account_type': {'$arrayElemAt': ['$account._type', 0]},
                'account': '$account._id',
                'accrual_doc': '$doc._id',
                'area_type': {'$cond': [
                    {'$lte': [{'$size': '$account.area._type'}, 2]},
                    {'$arrayElemAt': ['$account.area._type', 0]},
                    {'$arrayElemAt': ['$account.area._type', -2]},
                ]},
            }},
            {'$lookup': {
                'from': 'Account',
                'localField': 'account',
                'foreignField': '_id',
                'as': 'account',
            }},
            {'$unwind': '$account'},
            {'$project': {
                'services': 1,
                'account_type': 1,
                'area_type': 1,
                'entity': {'$cond': {
                    'if': {'$eq': ['$account.entity', None]},
                    'then': '$$REMOVE',
                    'else': '$account.entity',
                }},
                'accrual_doc': 1,
                'value': 1,
            }},
            {'$unwind': '$services'},
            {'$project': {
                'service_id': '$services.service_type',
                'value': '$services.value',
                'shortfalls': '$services.totals.shortfalls',
                'privileges': '$services.totals.privileges',
                'recalculations': '$services.totals.recalculations',
                'total': {'$add': [
                    '$services.value',
                    '$services.totals.shortfalls',
                    '$services.totals.privileges',
                    '$services.totals.recalculations'
                ]},
                'account_type': 1,
                'area_type': 1,
                'entity': 1,
                'accrual_doc': 1,
            }},
            {'$group': {
                '_id': {
                    'service_id': '$service_id',
                    'area_type': '$area_type',
                    'accrual_doc': '$accrual_doc',
                    'account_type': '$account_type',
                    'entity': '$entity',
                },
                'value': {'$sum': '$value'},
                'shortfalls': {'$sum': '$shortfalls'},
                'privileges': {'$sum': '$privileges'},
                'recalculations': {'$sum': '$recalculations'},
                'total': {'$sum': '$total'},
            }},
            {'$group': {
                '_id': {
                    'accrual_doc': '$_id.accrual_doc',
                    'account_type': '$_id.account_type',
                    'entity': '$_id.entity',
                },
                'services': {'$addToSet': {
                    'value': '$value',
                    'shortfalls': '$shortfalls',
                    'privileges': '$privileges',
                    'recalculations': '$recalculations',
                    'total': '$total',
                    'area_type': '$_id.area_type',
                    'service_id': '$_id.service_id'
                }}
            }}
        ]
        return pipeline

    def _get_debit_file_meta(self, accrual_doc, account_type, entity=None):
        header = dict(file_type='Начисления')
        doc = AccrualDoc.objects.get(pk=accrual_doc)

        header['doc_id'] = str(doc.id)
        header['doc_date'] = doc.date.isoformat()
        header['description'] = doc.description or ''
        header['house_address'] = doc.house.address
        header['house_id'] = str(doc.house.id)
        if account_type == 'PrivateTenant':
            header['type'] = 'Физические лица'
        elif account_type == 'LegalTenant':
            header.update(self.__get_legal_entity_meta(entity))
        return header

    def get_debit_files(self):
        """
        Метод формирует и сохраняет в self.files словари для файлов Начисления
        в разбивке по домам, документам начислений и контрагентам
        """
        def extract_penalties_summary(key):
            for s in penalty_summaries:
                if not set(s['_id'].values()).difference(set(key.values())):
                    return s['services']
            return None

        accrual_pipeline = self._get_debit_pipeline()
        accrual_summaries = list(Accrual.objects.aggregate(*accrual_pipeline))
        penalty_pipeline = self._get_penalties_pipeline()
        penalty_summaries = list(Accrual.objects.aggregate(*penalty_pipeline))

        for summary in accrual_summaries:
            file = dict()
            file.update(self._get_debit_file_meta(**summary['_id']))
            services = summary.pop('services')
            penalty_services = extract_penalties_summary(summary['_id'])
            services += (penalty_services or [])
            services_ids = {x['service_id'] for x in services}
            services_names = get_service_names(
                self.provider_id,
                list(services_ids),
            )
            for service in services:
                if not any([
                    service.get('value'),
                    service.get('shortfalls'),
                    service.get('privileges'),
                    service.get('recalculations'),
                    service.get('total'),
                ]):
                    continue
                area_type_dict = file.setdefault(
                    OUTPUT_AREA_TYPES[service['area_type']],
                    dict(),
                )
                penalties = area_type_dict.setdefault('penalties', 0)
                if service['service_id'] in PENALTY_SERVICE_TYPES_CHANGE:
                    area_type_dict['penalties'] += service['total']
                else:
                    services_list = area_type_dict.setdefault(
                        'services',
                        list(),
                    )
                    services_list.append(
                        {
                            'use_vat': False,
                            'vat': 0,
                            'vat_rate': 0,
                            'value': service['value'] / 100,
                            'shortfalls': service['shortfalls'] / 100,
                            'privileges': service['privileges'] / 100,
                            'recalculations': service['recalculations'] / 100,
                            'total': service['total'] / 100,
                            'service_id': str(service['service_id']),
                            'service_name': services_names.get(
                                service['service_id'],
                                {},
                            ).get(
                                'title',
                                '',
                            ),
                        }
                    )
            self.files.append(file)
        pass

    def get_credit_files(self):
        """
        Метод формирует и сохраняет в self.files словари для файлов Расщепление
        в разбивке по домам и контрагентам
        """
        agents = [{'accounts_type': 'PrivateTenant'}]
        legal_agents = self.distinct_legal_tenants()
        for lc, ids in legal_agents.items():
            agents.append({
                'accounts_list': ids,
                'accounts_type': 'LegalTenant',
            })

        # todo Отказ от вложенных циклов в пользу агрегации влечет за собой
        #  вмешательство в _ServicesBalance, на которое без
        #  понимания офсетов я не готов
        for agent in agents:
            for house in self.houses:
                house_credit = dict()
                header = self._get_credit_file_meta(house, agent)
                house_credit.update(header)
                for area_type in AREA_TYPES:
                    sb = ExportSummaryServicesBalance(
                        binds=self.binds,
                        area_type=area_type,
                        houses=[house],
                        **agent
                    )
                    sb.old_method = self.old_method

                    data, tariff_plans = sb.get_trial_balance(
                        self.date_from,
                        self.date_till,
                        return_tariff_plans=True,
                    )
                    data = self.format_credit_data(data, tariff_plans)
                    house_credit[OUTPUT_AREA_TYPES[area_type]] = data
                self.files.append(house_credit)

    def _format_vendors_data(self, data, house_id):
        files = []

        house = House.objects.get(pk=house_id)
        for contract_id, services in data.items():
            services_ids = {x['service_id'] for x in services}
            services_names = get_service_names(
                self.provider_id,
                list(services_ids),
            )

            file = dict()
            contract = LegalEntityContract.objects.get(pk=contract_id)
            entity = LegalEntity.objects.get(pk=contract.entity)
            file.update(self.__get_legal_entity_meta(entity))
            file.update({
                'house_id': str(house.id),
                'house_address': house.address,
                'file_type': 'Поставщики'
            })
            #  На файл поставщиков нет ТЗ, структура скопирована со старого
            crutch = file.setdefault('living_area', dict())
            for service in services:
                service['service_name'] = services_names.get(
                    service['service_id'], {}
                ).get(
                    'title', ''
                )
                service['service_id'] = str(service['service_id'])
            crutch['services'] = services
            files.append(file)
        return files

    def get_vendors_files(self):
        """
        Метод формирует и сохраняет в self.files словари для файлов Поставщики
        в разбивке по домам и поставщикам
        """
        for house in self.houses:
            vendors_data = dict()
            sb = VendorsServicesBalance(
                binds=self.binds,
                houses_ids=[house]
            )
            to = sb.get_credit_turnovers(
                self.date_from,
                self.date_till
            )
            for keys, values in to.items():
                if not keys[0]:
                    continue
                vendor_data = vendors_data.setdefault(keys[0], list())
                service = {
                    'service_id': keys[1],
                    'invoice': sum(values.values())
                }
                vendor_data.append(service)
            self.files.extend(self._format_vendors_data(vendors_data, house))
            pass

    def process(self):
        self.old_method = self._is_old_method()
        self.get_debit_files()
        self.get_credit_files()
        if self._provider_uses_vendors():
            self.get_vendors_files()
        json_files = [JSONFileCreator(file) for file in self.files]
        return ZipArchive(json_files).as_bytes()


def get_export_accruals_summary(provider_id, doc_ids, date_from,
                                date_till, binds=None, houses=None):
    export = ExportSummary(
        provider_id=provider_id,
        accrual_docs=doc_ids,
        date_from=date_from,
        date_till=date_till,
        binds=binds,
        houses=houses
    )
    return export.process()
