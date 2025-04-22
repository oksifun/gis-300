from api.v4.viewsets import HandyRouter
from app.legal_entity.api.v4.providers.views import ProvidersSearchViewSet

from .viewsets import (ContractHousesViewSet, CreateNewLegalEntityViewSet,
                       LegalEntityViewSet, LegalEntityContractViewSet,
                       MassCreateLegalEntityService,
                       UpdateProducerViewSet, LegalEntityServiceViewSet)

legal_entity_router = HandyRouter()

# Для работы с моделью LegalEntityProviderBind
legal_entity_router.register(
    'models/legal_entity',
    LegalEntityViewSet,
    basename='legal_entity'
)
# Для работы с моделью LegalEntityContract
legal_entity_router.register(
    'models/entity_contract',
    LegalEntityContractViewSet,
    basename='entity_contract'
)
legal_entity_router.register(
    'models/create_legal_entity',
    CreateNewLegalEntityViewSet,
    basename='create_legal_entity'
)
legal_entity_router.register(
    'models/update_producers',
    UpdateProducerViewSet,
    basename='update_producers'
)
legal_entity_router.register(
    'models/contract_houses',
    ContractHousesViewSet,
    basename='contract_houses'
)
legal_entity_router.register(
    'models/entity_contract_services',
    LegalEntityServiceViewSet,
    basename='entity_contract_services'
)
legal_entity_router.register(
    'models/create_entity_contract_services',
    MassCreateLegalEntityService,
    basename='create_entity_contract_services'
)

# Работа с Provider
legal_entity_router.register(
    'search/provider',
    ProvidersSearchViewSet,
    basename='search_provider'
)
