# -*- coding: utf-8 -*-
import json
import re
from abc import ABC, abstractmethod
from itertools import groupby
from uuid import uuid4

from bson import ObjectId
from pathlib import PurePath

from app.c300.utils.strings import sanitize_string
from app.house.models.house import House
from app.legal_entity.models.legal_entity_contract import LegalEntityContract
from app.legal_entity.models.legal_entity_provider_bind import (
    LegalEntityProviderBind
)
from processing.data_producers.associated.services import get_service_names


class SummaryCreator(ABC):
    """Абстрактный класс для получения summary"""
    
    def __init__(self, binds):
        self.binds = binds
        self.penalty_id = ObjectId('000000000000000000000000')

    @property
    @abstractmethod
    def model(self):
        pass

    @property
    @abstractmethod
    def file_type(self):
        pass
    
    @property
    @abstractmethod
    def match(self) -> dict:
        pass

    @property
    @abstractmethod
    def service_template(self):
        pass
    
    @property
    @abstractmethod
    def pipeline(self) -> list:
        pass

    def result(self):
        result = list(self.model.objects.aggregate(*self.pipeline))
        return result


class DataTransformer:
    """
    @deprecated
    Класс для преобразования summary в нужный формат.
    """
    
    @classmethod
    def rename_area_type(cls, area_type: str) -> str:
        """Переименование типа помещения.
        
        Пример:
            LivingArea -> living_area
        """
        splitted = re.sub('([A-Z][a-z]+)', r' \1',
                          re.sub('([A-Z]+)', r' \1', area_type)).split()
        return "_".join(splitted).lower()

    @classmethod
    def add_service_names(
            cls,
            summaries: list,
            provider_id: str,
            values_list: list,
    ) -> list:
        """Добавление service_name к _id."""
        services_ids = {record['_id']['service_id'] for record in summaries}
        services_names = get_service_names(provider_id, services_ids)
        for summary in summaries:
            service_id = summary['_id'].pop('service_id')
            summary['_id']['service']['service_id'] = str(service_id)
            summary['_id']['service']['service_name'] = (services_names.get(
                service_id
            ) or {}).get('title', 'Пени')
            for value in values_list:
                summary['_id']['service'][value] = summary.pop(value) / 100
                
        return summaries
    
    @classmethod
    def add_house_address(cls, summaries: list) -> list:
        """Добавление house_address к _id."""
        houses_ids = {record['_id']['house_id'] for record in summaries}
        houses = House.objects(pk__in=houses_ids).only('address').as_pymongo()
        houses_addresses = {house['_id']: house['address'] for house in houses}
        for summary in summaries:
            summary['_id']['house_address'] = (
                    houses_addresses[summary['_id']['house_id']]
            )
        return summaries

    @classmethod
    def split_by_files(cls, summaries: list) -> list:
        """Делит summary на файлы.
        
        Данные объединяются в один файл, если:
        — один дом
        — один тип («Начисления», «Расщепление», «Поставщики»)
        — все физ. лица в один файл, каждый контракт юр. лица (если нет
        контракта, то каждое юр. лицо) в один файл
        """
        files = []
        key_function = lambda x: {
            'house_id': x['_id']['house_id'],
            'house_address': x['_id']['house_address'],
            'file_type': x['_id']['file_type'],
            'account_type': x['_id']['account_type'],
            'contract': x['_id'].get('contract'),
        }
        value_function = lambda x: {
            'area_type': x['_id']['area_type'],
            'service': x['_id']['service'],
        }
        for key, group in groupby(summaries, key_function):
            files.append({
                **key,
                'services': [value_function(service) for service in group]
            })
        return files
    
    @classmethod
    def group_services(cls, files: list) -> list:
        """Объединяет услуги по типу помещений."""
        area_types = ('living_area', 'not_living_area', 'parking_area')
        service_types = ('services', 'penalties')
        for file in files:
            total = 0
            services = file.pop('services')
            services_result = dict()
            for area_type in area_types:
                services_result[area_type] = (
                    {service_type: [] for service_type in service_types}
                )
            for service in services:
                key = cls.rename_area_type(service.pop('area_type'))
                secondary_key = (
                    'penalties'
                    if service['service']['service_id'] == 'penalties'
                    else 'services'
                )
                services_result[key][secondary_key].append(service['service'])
                total += service['service'].get('paid', 0)
                total += service['service'].get('total', 0)
                total += service['service'].get('invoice', 0)
            file['services'] = services_result
            file['total'] = total
        return files
   
    @classmethod
    def apply_pipeline(
            cls,
            summaries: list,
            provider_id: str,
            values_list: list,
    ) -> list:
        """Применение всех преобразований."""
        return cls.group_services(
                cls.split_by_files(
                    cls.add_house_address(
                        cls.add_service_names(
                            summaries,
                            provider_id,
                            values_list,
                        )
                    ),
                ),
        )


class JSONFileCreator(ABC):
    """Абстрактный класс для создания json-файлов."""
    
    def __init__(self, data: dict):
        self.data = data
        self.account_type = (
            'Юридические лица' if data.get('account_type') == 'LegalTenant'
            else 'Физические лица'
        )
        self.address = sanitize_string(data.get('house_address', 'Неизвестный'))
        self.file_type = data.get('file_type', '')

    
    @property
    def services(self):
        return self.data['services']
    
    @property
    def contractor(self):
        contract_id = self.data.get('contract')
        if not contract_id:
            return dict()
        contract = LegalEntityContract.objects(
            pk=contract_id,
        ).as_pymongo().get()
        contractor = LegalEntityProviderBind.objects(
            entity=contract['entity'],
            provider=contract['provider'],
        ).as_pymongo().get()
        return(dict(
            contragent_name=contractor['entity_details'][0]['short_name'],
            contragent_inn=contractor['entity_details'][0].get('inn'),
            contragent_kpp=contractor['entity_details'][0].get('kpp'),
            contract_name=contract.get('number'),
            contract_date=(
                contract['date'].replace(microsecond=0).isoformat()
                if contract.get('date', None)
                else None
            ),
        ))
    
    @property
    def content(self) -> str:
        """Возвращает содержание файла."""
        # data = {
        #     **self.header,
        #     **self.services,
        #     **self.contractor,
        # }
        return json.dumps(self.data, ensure_ascii=False, indent=4)
    
    @property
    def file_name(self) -> str:
        """Возвращает имя файла."""
        postfix = uuid4().time_mid
        return f"{self.file_type}_{postfix}.json"
    
    @property
    def file_path(self) -> PurePath:
        """Возвращает путь к файлу не включая имя файла."""
        return PurePath(self.address)
    
    @property
    def full_file_path(self) -> PurePath:
        """Возвращает полный путь к файлу."""
        return PurePath(self.file_path, self.file_name)

