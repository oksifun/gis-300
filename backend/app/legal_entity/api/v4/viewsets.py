from django.http import HttpResponse, JsonResponse
from mongoengine import ValidationError
from rest_framework import status
from rest_framework.decorators import action

from api.v4.authentication import RequestAuth
from api.v4.serializers import PrimaryKeySerializer, json_serializer
from api.v4.universal_crud import BaseCrudViewSet
from api.v4.utils import permission_validator
from api.v4.viewsets import BaseLoggedViewSet
from app.legal_entity.models.core import (LegalEntityDetailsEmbedded,
                                          LegalEntityBankAccountEmbedded)
from app.legal_entity.models.legal_entity_contract import LegalEntityContract
from app.legal_entity.models.legal_entity_provider_bind import (
    LegalEntityProviderBind)
from app.legal_entity.models.legal_entity_service import EntityAgreementService
from app.legal_entity.tasks.update_vendor import \
    vendor_apply_to_offsets
from app.house.models.house import House

from .serializers import (AgreementSerializer, ContractHousesSerializer,
                          CreateNewLegalEntitySerializer, LegalEntitySerializer,
                          LegalEntityContractSerializer,
                          LegalEntityServiceSerializer,
                          LegalEntityServicesCreateSerializer,
                          LegalEntityServiceListSerializer,
                          LegalEntityServiceUpdateSerializer,
                          UpdateProducerUpdateSerializer,
                          UpdateProducerCreateSerializer)


class LegalEntityViewSet(BaseCrudViewSet):
    http_method_names = ['get', 'post']
    serializer_class = LegalEntitySerializer

    def get_queryset(self):
        request_auth = RequestAuth(self.request)
        binds = request_auth.get_binds()
        legal_binds = LegalEntityProviderBind.objects(
            LegalEntityProviderBind.get_binds_query(binds),
        )
        return legal_binds


class ContractHousesViewSet(BaseLoggedViewSet):
    def list(self, request):
        request_auth = RequestAuth(self.request)
        serializer = ContractHousesSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        houses_services = EntityAgreementService.objects(
            contract=serializer.validated_data['contract'],
            entity=serializer.validated_data['vendor'],
            provider=request_auth.get_provider_id(),
        ).only(
            'house',
        ).as_pymongo()
        houses_services = list(houses_services)
        data = {}
        houses = {s['house'] for s in houses_services if s.get('house')}
        if houses:
            addresses = House.objects(
                id__in=houses,
            ).only(
                'address',
                'street',
                'street_only',
            ).as_pymongo()
            addresses = {
                address['_id']: {
                    'address': address['address'],
                    'street': address['street'],
                    'street_only': address['street_only'],
                }
                for address in addresses
            }
            data['houses'] = [
                {
                    '_id': house,
                    'address': addresses[house]['address'],
                    'street': addresses[house]['street'],
                    'street_only': addresses[house]['street_only'],
                }
                for house in houses
            ]
        return JsonResponse(
            data=data,
            json_dumps_params={'default': json_serializer},
        )


class CreateNewLegalEntityViewSet(BaseLoggedViewSet):
    @permission_validator
    def create(self, request):
        request_auth = RequestAuth(self.request)
        serializer = CreateNewLegalEntitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data[
            'legal_provider'] = request_auth.get_provider_id()
        LegalEntityProviderBind.create_new_legal_binds(
            **serializer.validated_data
        )
        return HttpResponse(status=status.HTTP_200_OK)


class UpdateProducerViewSet(BaseLoggedViewSet):
    @permission_validator
    def create(self, request):
        serializer = UpdateProducerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entity_details = serializer.validated_data['entity_details']
        producer = serializer.validated_data['producer']
        producer = LegalEntityProviderBind.objects(id=producer).first()
        if not producer:
            raise ValidationError('Поставщика не сущесвует')
        entity_details = LegalEntityDetailsEmbedded(**entity_details)
        if producer.entity_details:
            producer.entity_details.append(entity_details)
        else:
            producer.entity_details = [entity_details]
        producer.save()
        data = LegalEntitySerializer(producer).data
        return JsonResponse(data=data)

    @permission_validator
    def partial_update(self, request, pk):
        serializer = UpdateProducerUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pk = PrimaryKeySerializer.get_validated_pk(pk)
        entity_details = serializer.validated_data.get('entity_details')
        bank_accounts = serializer.validated_data.get('entity_bank_accounts')
        producer = LegalEntityProviderBind.objects(id=pk).first()
        if not producer:
            raise ValidationError('Поставщика не сущесвует')

        if bank_accounts:
            producer.entity_bank_accounts = [
                LegalEntityBankAccountEmbedded(**bank_account)
                for bank_account in bank_accounts
            ]
        if entity_details:
            if producer.entity_details:
                producer.entity_details[-1] = LegalEntityDetailsEmbedded(
                    **entity_details
                )
            else:
                producer.entity_details = [entity_details]
        producer.save()
        data = LegalEntitySerializer(producer).data
        return JsonResponse(data=data)


class LegalEntityContractViewSet(BaseCrudViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete']
    serializer_class = LegalEntityContractSerializer

    def get_queryset(self):
        request_auth = RequestAuth(self.request)
        current_provider = request_auth.get_provider_id()
        return LegalEntityContract.objects(
            provider=current_provider
        )

    @permission_validator
    def destroy(self, request, id, *args, **kwargs):
        pk = PrimaryKeySerializer.get_validated_pk(id)
        EntityAgreementService.mark_deleted(contract=pk)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['get', 'post'])
    def agreements(self, request, *args, **kwargs):
        """ Получение списка соглашений или создание нового """
        return self.operate_list_objects(
            request=request,
            object_name='agreements',
            object_serializer=AgreementSerializer
        )

    @action(
        detail=True,
        methods=['get', 'patch', 'delete'],
        url_path='agreements/(?P<agreement_id>\w+)'
    )
    def agreement(self, request, agreement_id, *args, **kwargs):
        """ Работа с одним соглашением (удаление/редактирование/получение) """
        pk = PrimaryKeySerializer.get_validated_pk(agreement_id)
        if request.method == 'DELETE':
            EntityAgreementService.mark_deleted(agreement=pk)
        return self.operate_one_object(
            request=request,
            object_id=agreement_id,
            object_name='agreements',
            object_serializer=AgreementSerializer
        )


class LegalEntityServiceViewSet(BaseCrudViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete']
    serializer_classes = {
        'create': LegalEntityServiceSerializer,
        'retrieve': LegalEntityServiceSerializer,
        'list': LegalEntityServiceListSerializer,
        'partial_update': LegalEntityServiceUpdateSerializer,
        'destroy': LegalEntityServiceSerializer,
    }

    def get_serializer_class(self):
        return self.serializer_classes[self.action]

    def get_queryset(self):
        request_auth = RequestAuth(self.request)
        current_provider = request_auth.get_provider_id()
        return EntityAgreementService.objects(provider=current_provider)

    @permission_validator
    def partial_update(self, request, id):
        id = PrimaryKeySerializer.get_validated_pk(id)
        serializer = self.get_serializer_class()(data=request.data,
                                                 partial=True)
        serializer.is_valid(raise_exception=True)
        instance = EntityAgreementService.objects(id=id).get()
        data = instance.update(**serializer.validated_data)
        return JsonResponse(data=LegalEntityServiceSerializer(data).data)


class MassCreateLegalEntityService(BaseLoggedViewSet):
    http_method_names = ['post']

    @permission_validator
    def create(self, request, *args, **kwargs):
        serializer = LegalEntityServicesCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        houses = serializer.validated_data.pop('houses')
        services = list()
        for house in houses:
            data = serializer.validated_data
            data['house'] = house
            service = EntityAgreementService(**data)
            services.append(service)
        new_objs = EntityAgreementService.objects.insert(services)
        for service in new_objs:
            vendor_apply_to_offsets.delay(service.id)
        return JsonResponse(
            data=LegalEntityServiceSerializer(new_objs, many=True).data,
            status=status.HTTP_201_CREATED,
            safe=False,
        )
