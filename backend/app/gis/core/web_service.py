from sys import modules

from pathlib import Path
from importlib import import_module

from app.gis.core.soap_client import SoapClient


class ServiceMeta(type):
    """
    Позволяет всем внутренним (вложенным) классам иметь ссылку на внешний класс
    """
    def __new__(mcs, name, parents, dct):
        """
        Выполняется даже если НЕ создавать класс-наследник
        """
        cls: type = super().__new__(mcs, name, parents, dct)  # outer

        for inner in dct.values():
            if isinstance(inner, type):  # ~ inspect.isclass
                assert hasattr(inner, '_service'), \
                    f"В классе сервиса {name} найден класс {inner.__name__}" \
                    " без ссылки на внешний класс"
                inner._service = cls  # двойное подчеркивание ~ _[class_name]_

                if hasattr(cls, 'IS_COMMON') and cls.IS_COMMON:
                    if hasattr(inner, 'IS_ANONYMOUS'):
                        inner.IS_ANONYMOUS = cls.IS_COMMON
                    if hasattr(inner, 'IS_HOMELESS'):
                        inner.IS_HOMELESS = cls.IS_COMMON
        return cls


class WebService(metaclass=ServiceMeta):

    # region ПАРАМЕТРЫ СЕРВИСА
    IS_COMMON: bool = False  # сервис с анонимными операциями?

    SERVICE_NAME: str = None  # ИЛИ имя класса (БЕЗ Service и БЕЗ Async)
    TARGET_NAMESPACE: str = None  # ИЛИ имя файла модуля с '_' вместо '-'

    # ...ext-bus-[module-file-name]-service/services/[ClassName]Async
    SERVICE_PATH = 'app.gis.services'

    SERVICE_MODULES: dict = {
        'OrgRegistryCommon':   'org_registry_common',
        'NsiCommon':           'nsi_common',
        'Nsi':                 'nsi',
        'HouseManagement':     'house_management',
        'ManagementContracts': 'contracts',
        'DeviceMetering':      'device_metering',
        'Bills':               'bills',
    }  # TODO добавлять новые сервисы

    OPERATION_SERVICES = {
        'exportOrgRegistry': 'OrgRegistryCommon',
        'exportNsiList': 'NsiCommon',
        'exportNsiItem': 'NsiCommon',
        'exportNsiPagingItem': 'NsiCommon',
        'exportDataProviderNsiItem': 'Nsi',
        'importAdditionalServices': 'Nsi',
        'importMunicipalServices': 'Nsi',
        'importGeneralNeedsMunicipalResource': 'Nsi',
        # 'exportDataProviderPagingNsiItem': 'Nsi',
        # 'importOrganizationWorks': 'Nsi',
        # 'importCapitalRepairWork': 'Nsi',
        # 'importCommunalInfrastructureSystem': 'Nsi',
        # 'importBaseDecisionMSP': 'Nsi',
        'exportCAChData': 'ManagementContracts',
        'importCharterData': 'ManagementContracts',
        'exportBriefBasicHouse': 'HouseManagement',
        'exportBriefApartmentHouse': 'HouseManagement',
        'exportHouseData': 'HouseManagement',
        'importHouseUOData': 'HouseManagement',
        'exportAccountData': 'HouseManagement',
        'importAccountData': 'HouseManagement',
        'exportMeteringDeviceData': 'HouseManagement',
        'importMeteringDeviceData': 'HouseManagement',
        # 'importHouseESPData': 'HouseManagement',
        # 'importHouseOMSData': 'HouseManagement',
        # 'importHouseRSOData': 'HouseManagement',
        # 'exportAccountIndividualServices': 'HouseManagement',
        # 'importAccountIndividualServices': 'HouseManagement',
        'exportMeteringDeviceHistory': 'DeviceMetering',
        'importMeteringDeviceValues': 'DeviceMetering',
        'exportNotificationsOfOrderExecution': 'Bills',
        'exportPaymentDocumentData': 'Bills',
        'importPaymentDocumentData': 'Bills',
        'withdrawPaymentDocumentData': 'Bills',
        'importAcknowledgment': 'Bills',
    }  # TODO добавлять новые операции
    # endregion ПАРАМЕТРЫ СЕРВИСА

    _clients: dict = {}

    def __init__(self, *args, **kwargs):

        raise RuntimeWarning("Не нужно создавать экземпляр класса веб-сервиса")

    @classmethod
    def soap_client(cls, debug_mode: bool = False) -> SoapClient:
        """
        Вернуть или создать новый экземпляр SOAP-клиента для сервиса
        """
        client_name: str = f"_{cls.__name__}" if debug_mode else cls.__name__

        if client_name in cls._clients:
            soap_client = cls._clients[client_name]  # возвращаем кэшированный
        else:
            soap_client = SoapClient(cls, debug_mode)  # экземпляр клиента
            cls._clients[client_name] = soap_client  # кэшируем экземпляр

        return soap_client

    @classmethod
    def get_name(cls) -> str:
        """
        Наименование веб-сервиса

        Совпадает с наименованием класса, если не задан атрибут SERVICE_NAME
        """
        DENIED: list = ['async', 'service']  # не должны быть в названии класса

        if not cls.SERVICE_NAME:
            assert all(sub not in cls.__name__.lower() for sub in DENIED), \
                'Имя класса веб-сервиса не должно содержать "Async" и "Service"'
            cls.SERVICE_NAME = cls.__name__
            # sub(r'(Service|Async)', '', cls.__name__)

        return cls.SERVICE_NAME  # ServiceName[Async] - Async добавляется

    @classmethod
    def get_tns(cls) -> str:
        """
        Целевое пространство имен веб-сервиса

        Совпадает с именем файла модуля, если не задан атрибут TARGET_NAMESPACE
        """
        if not cls.TARGET_NAMESPACE:
            module_name: str = cls.__module__  # наименование модуля

            # рекомендуемый способ получения модуля
            service_module = modules[module_name]

            # имя файла без расширения
            module_file_name = Path(service_module.__file__).stem

            # имя файла не может содержать '-'
            cls.TARGET_NAMESPACE = module_file_name.replace('_', '-')

        return cls.TARGET_NAMESPACE

    @classmethod
    def operation(cls, operation_name: str):  # -> type
        """
        Получить соответствующий названию класс операции
        """
        service_name: str = cls.OPERATION_SERVICES.get(operation_name)
        assert service_name, \
            f"Сервис ГИС ЖКХ не определен для операции {operation_name}"
        module_path = f"{cls.SERVICE_PATH}.{cls.SERVICE_MODULES[service_name]}"

        service_module = import_module(module_path)  # __import__(module_path)
        service_class = getattr(service_module, service_name)
        service_operation = getattr(service_class, operation_name)

        return service_operation  # класс (не экземпляр) операции
