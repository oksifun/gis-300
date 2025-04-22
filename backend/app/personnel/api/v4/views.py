from datetime import datetime
import logging

from bson import ObjectId
from django.http import (
    JsonResponse,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
)
from mongoengine import ValidationError, Q, DoesNotExist
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from api.v4.authentication import RequestAuth
from api.v4.permissions import SuperUserOnly
from api.v4.serializers import PrimaryKeySerializer
from api.v4.universal_crud import BaseCrudViewSet, ModelFilesViewSet
from api.v4.utils import permission_validator
from api.v4.viewsets import (
    BaseLoggedViewSet,
    SerializationMixin,
)
from app.house.models.house import House
from app.permissions.tasks.binds_permissions import process_house_binds_models
from app.personnel.api.v4.serializers import (
    WorkerSerializer,
    WorkerBaseInfoSerializer,
    WorkerListSerializer,
    REQUIRED_FIELDS,
    SupportTicketUpdateSerializer,
    DepartmentsSerializer,
    DepartmentUpdateSerializer,
    DepartmentsTreeSerializer,
    DepartmentPublicUpdateSerializer,
    SystemDepartmentsSerializer,
    ResendActivationMailSerializer,
    WorkerDocSerializer,
    ServicedHousesSerializer,
    WorkerSearchSerializer,
    ModelWorkerSearchSerializer,
    VCardSerializer,
    AccessWorkerSerializer,
    CopyWorkerPermissionsSerializer,
    DismissWorkerSerializer,
    WorkerManagementSerializer,
    MessengerTemplateSerializer
)
from app.personnel.models.department import Department
from app.personnel.models.personnel import (
    Worker,
    WorkerSupportTimer,
    MessengerTemplate,
)
from app.personnel.models.system_department import SystemDepartment
from app.auth.models.actors import Actor
from lib.passwords import qwerty_password
from processing.data_producers.associated.base import get_binded_houses
from processing.models.billing.house_group import HouseGroup
from processing.models.billing.provider.main import Provider
from processing.models.exceptions import CustomValidationError
from processing.models.permissions import Permissions


logger = logging.getLogger('c300')


class WorkerViewSet(BaseCrudViewSet):
    # Разрешенные методы
    http_method_names = ['get']
    # Передаем сериализатор модели, на основе которого будет проинспектирована
    # модель и drf узнает все о ее полях
    serializer_class = WorkerSerializer
    slug = 'hr'

    def get_queryset(self):
        request_auth = RequestAuth(self.request)
        provider = request_auth.get_provider_id()
        match_query = {
            '_type': 'Worker',
            'is_deleted': {'$ne': True},
        }
        if request_auth.is_super():
            serializer = WorkerListSerializer(data=self.request.query_params)
            serializer.is_valid(raise_exception=True)
            if not self.kwargs.get('id'):
                match_query['provider._id'] = \
                    serializer.validated_data.get('provider__id', provider)
        else:
            match_query['provider._id'] = provider
            binds_query = Worker.get_binds_query(request_auth.get_binds())
            match_query.update(binds_query)
        return Worker.objects(__raw__=match_query).only(*REQUIRED_FIELDS)


class WorkerBaseInfoViewSet(BaseCrudViewSet):
    # Разрешенные методы
    http_method_names = ['get']
    # Передаем сериализатор модели, на основе которого будет проинспектирована
    # модель и drf узнает все о ее полях
    serializer_class = WorkerBaseInfoSerializer
    slug = 'apartment_meters'

    def get_queryset(self):
        request_auth = RequestAuth(self.request)
        provider = request_auth.get_provider_id()
        match_query = {
            '_type': 'Worker',
            'is_deleted': {'$ne': True},
            'provider._id': provider,
            'is_super': {'$ne': True}
        }
        binds_query = Worker.get_binds_query(request_auth.get_binds(), True)
        match_query.update(binds_query)
        workers = Worker.objects(__raw__=match_query).only('id', 'str_name')
        return workers


class WorkerTicketAccessLevelViewSet(BaseCrudViewSet):
    http_method_names = ['patch']
    slug = 'worker_rules'
    serializer_classes = {
        'partial_update': SupportTicketUpdateSerializer,
    }

    def get_serializer_class(self):
        return self.serializer_classes[self.action]

    def get_queryset(self):
        request_auth = RequestAuth(self.request)
        binds = request_auth.get_binds()
        return Worker.objects(
            Worker.get_binds_query(binds),
        )


class DepartmentsViewSet(BaseCrudViewSet):
    serializer_classes = {
        'list': DepartmentsSerializer,
        'retrieve': DepartmentsSerializer,
        'partial_update': DepartmentUpdateSerializer,
        'create': DepartmentUpdateSerializer,
    }
    slug = 'departments'
    permission_classes = (SuperUserOnly,)

    def get_serializer_class(self):
        return self.serializer_classes[self.action]

    def get_queryset(self):
        return Department.objects(
            is_deleted__ne=True,
        )


class DepartmentsPublicViewSet(BaseCrudViewSet):
    serializer_classes = {
        'list': DepartmentsTreeSerializer,
        'retrieve': DepartmentsTreeSerializer,
        'partial_update': DepartmentPublicUpdateSerializer,
    }
    http_method_names = ['get', 'patch']
    paginator = None

    # slug = 'hr'

    def get_serializer_class(self):
        return self.serializer_classes[self.action]

    def get_queryset(self):
        request_auth = RequestAuth(self.request)
        binds = request_auth.get_binds()
        return Department.objects(
            Department.get_binds_query(binds),
            provider=request_auth.get_provider_id(),
            is_deleted__ne=True,
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset()).limit(100)
        data = self.add_labors(list(queryset))
        serializer = self.get_serializer(data, many=True)
        return Response(serializer.data)

    @staticmethod
    def add_labors(departments):
        positions = {}
        for department in departments:
            for position in department.positions:
                positions[position.id] = position
                position.workers = []
        labors = list(
            Worker.objects(
                department__id__in=[d.id for d in departments],
                is_deleted__ne=True,
            ).only(
                'id',
                'str_name',
                'position.id',
                'has_access',
                'is_dismiss',
                'dismiss_date',
                'phones',
                'email',
                'settings'
            ).as_pymongo(),
        )
        labors = sorted(
            labors,
            key=lambda i: (i.get('is_dismiss', False), i['str_name']),
        )
        for labor in labors:
            if not labor.get('position'):
                continue
            if labor['position']['_id'] in positions:
                labor['id'] = labor.pop('_id')
                positions[labor['position']['_id']].workers.append(labor)
        return departments


class SystemDepartmentsViewSet(BaseCrudViewSet):
    serializer_class = SystemDepartmentsSerializer
    slug = 'departments'
    permission_classes = (SuperUserOnly,)
    http_method_names = ['get']

    def get_queryset(self):
        return SystemDepartment.objects().all()


class ResendPasswordMailViewSet(BaseLoggedViewSet):
    slug = 'worker_rules'

    @permission_validator
    def create(self, request):
        logger.debug('ResendPasswordMailViewSet POST/create')
        serializer = ResendActivationMailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        worker_id = serializer.validated_data.get('worker_id')
        if not worker_id:
            logger.error('Нет id воркера!')
            return Response(status=HTTP_400_BAD_REQUEST)

        try:
            worker = Worker.objects.get(id=worker_id)
        except DoesNotExist as dne:
            logger.error('Воркер %s не найден: %s', worker_id, dne)
            return Response(status=HTTP_404_NOT_FOUND)

        actor = Actor.get_or_create_actor_by_worker(worker, has_access=True)

        if not worker.email:
            raise ValidationError("Отсутствует email")
        if not worker.has_access:
            raise ValidationError("Отсутствует доступ в систему.")
        if worker.activation_code or worker.activation_step:
            raise ValidationError("Пользователь не прошёл активацию")

        password = worker.generate_new_password()
        password_hash = worker.password_hash(password)
        worker.password = actor.password = password_hash
        worker.save()
        actor.save()

        try:
            worker.send_new_password_mail(password)
        except Exception as error:
            raise ValidationError(f"Ошибка отправки письма {error}")
        return JsonResponse(data=dict(result="Письмо отправлено"))


class WorkersViewSet(BaseCrudViewSet):
    serializer_class = WorkerDocSerializer
    http_method_names = ['get', 'patch', "post"]
    slug = 'hr'

    def get_queryset(self):
        request_auth = RequestAuth(self.request)
        binds_query = Worker.get_binds_query(request_auth.get_binds())
        if request_auth.is_super():
            provider = self.request.query_params.get('provider__id')
            if not self.kwargs.get('id') and not provider:
                binds_query = Q(
                    _binds__pr=request_auth.get_provider_id(),
                )
        return Worker.objects(
            binds_query,
            _type='Worker',
            is_deleted__ne=True,
        )

    @staticmethod
    def get_params(data):
        worker = Worker.objects(id=data.data['id']).first()
        elective = False
        department = Department.objects(
            id=worker.department.id
        ).as_pymongo().only('system_department').first()
        if department and department.get('system_department'):
            sys_department = SystemDepartment.objects(
                id=department['system_department']['_id']
            ).as_pymongo().only('title').first()
            if (
                    sys_department
                    and sys_department['title']
                    in SystemDepartment.ELECTIVE_DEPARTMENTS
            ):
                elective = True

        return {
            'is_active': worker.is_activated,
            'elective': elective,
        }

    def retrieve(self, request, *args, **kwargs):
        data = super().retrieve(request, *args, **kwargs)
        data.data.update(self.get_params(data))
        return data

    def create(self, request, *args, **kwargs):
        self.infest_request_data_by_provider(request, as_object=True)
        return super().create(request, *args, **kwargs)


class WorkerFilesViewSet(ModelFilesViewSet):
    model = Worker
    slug = 'hr'

    def get_queryset(self):
        # Документы только для данной организации
        request_auth = RequestAuth(self.request)
        binds = request_auth.get_binds()
        return Worker.objects(
            Worker.get_binds_query(binds),
            _type=['Worker'],
            is_deleted__ne=True,
        )


class WorkerServicedHousesViewSet(BaseLoggedViewSet):
    slug = 'worker_serviced_facilities'

    def retrieve(self, request, pk):
        request_auth = RequestAuth(request)
        provider_id = request_auth.get_provider_id()
        pk = PrimaryKeySerializer.get_validated_pk(pk)
        worker = Worker.objects(
            Worker.get_binds_query(request_auth.get_binds()),
            id=pk,
        ).only(
            'id',
            "_binds_permissions",
        ).as_pymongo().get()
        houses = House.objects(
            House.get_binds_query(request_auth.get_binds()),
            id__in=get_binded_houses(provider_id),
        )
        worker_houses = []
        if (
                worker.get('_binds_permissions')
                and worker['_binds_permissions'].get('hg')
        ):
            house_group = HouseGroup.objects(
                pk=worker['_binds_permissions']['hg'],
            ).only(
                'houses',
            ).as_pymongo().get()
            worker_houses = house_group['houses']
        data = ServicedHousesSerializer(houses, many=True).data
        for data_house in data:
            if ObjectId(data_house['id']) in worker_houses:
                data_house['worker_serviced'] = True
            else:
                data_house['worker_serviced'] = False
        return JsonResponse(data={"serviced_houses": data})

    @permission_validator
    def partial_update(self, request, pk):
        from app.caching.tasks.cache_update import create_fias_tree_cache

        request_auth = RequestAuth(self.request)
        provider_id = request_auth.get_provider_id()
        pk = PrimaryKeySerializer.get_validated_pk(pk)
        serializer = ServicedHousesSerializer(
            data=request.data['serviced_houses'],
            many=True,
        )
        serializer.is_valid(raise_exception=True)
        houses = House.objects(
            House.get_binds_query(request_auth.get_binds()),
            id__in=get_binded_houses(provider_id),
        ).only(
            'id',
        )
        houses = [h['_id'] for h in houses.as_pymongo()]

        worker = Worker.objects(
            Worker.get_binds_query(request_auth.get_binds()),
            id=pk,
        ).get()
        permissions = Permissions.objects(
            _id=f"Account:{str(worker.id)}",
        ).first()
        if not permissions:
            permissions = Permissions(
                actor_id=worker.id,
                _id=f"Account:{str(worker.id)}",
                actor_type="Account",
                current={},
                granular={},
                general={},
            )
            permissions.save()
        if permissions.granular.get('House') is None:
            permissions.granular['House'] = {}
        for house in serializer.validated_data:
            serviced = house.get('worker_serviced', False)
            if house['id'] not in houses:
                raise DoesNotExist(f'House is not found {house}')
            self.do_action_with_house(permissions, serviced, house['id'])
        permissions.save()
        house_group, is_new = \
            self.get_or_create_house_group(worker.id, provider_id)
        worker._binds_permissions.hg = house_group
        worker.save()

        actor = worker.get_actor()
        actor.binds_permissions.hg = house_group
        actor.save()

        create_fias_tree_cache.delay(
            provider_id=worker.provider.id,
            account_id=worker.id,
        )
        if is_new:
            for house in houses:
                process_house_binds_models.delay(house)
        return HttpResponse('success')

    @staticmethod
    def do_action_with_house(permissions, to_live, house):
        if to_live:
            permission = [dict(
                permissions=dict(
                    c=True,
                    r=True,
                    u=True,
                    d=True
                ),
                _id=ObjectId()
            )]

            permissions.granular['House'].update({str(house): permission})
            if (
                    permissions.current.get('House')
                    and permissions.current['House'].get('allow')
                    and all(
                permissions.current['House']['allow'][act]
                for act in permissions.current['House']['allow']
            )
            ):
                actions = permissions.current['House']['allow']
                for action in actions.values():
                    if house not in action:
                        action.append(house)
            else:
                actions = {
                    "c": [house],
                    "r": [house],
                    "u": [house],
                    "d": [house],
                }
                permissions.current.update(
                    {'House': {'allow': actions}}
                )

        else:
            if (
                    permissions.granular.get('House')
                    and permissions.granular['House'].get(str(house))
            ):
                del permissions.granular['House'][str(house)]
                for action in permissions.current['House']['allow']:
                    permissions.current['House']['allow'][action].remove(house)

    def get_or_create_house_group(self, account_id, provider_id):
        from processing.models.billing.house_group import HouseGroup
        houses = self.get_houses_from_permission(account_id)
        binded_houses = get_binded_houses(provider_id)
        houses = list(set(houses) & set(binded_houses))
        houses.sort()
        house_group = HouseGroup.objects(
            provider=provider_id,
            houses=houses,
            hidden=True,
        ).only(
            'id',
        ).as_pymongo().first()
        if house_group:
            return house_group['_id'], False
        hg = HouseGroup(
            houses=houses,
            title='{} {}'.format(
                len(houses),
                'домов' if str(len(houses))[-1] == '1' else 'дом',
            ),
            provider=provider_id,
            hidden=True,
        )
        hg.save()
        return hg.id, True

    @staticmethod
    def get_houses_from_permission(account_id):
        from processing.models.permissions import Permissions
        acc_permission = Permissions.objects(
            __raw__={
                '_id': 'Account:{}'.format(account_id)
            },
        ).as_pymongo()
        # Если права найдены
        if not acc_permission:
            return []
        acc_permission = acc_permission[0]
        # Поиск прав на дома
        house_permissions = acc_permission.get('granular', {}).get('House')
        if not house_permissions:
            return []
        return [ObjectId(key) for key in house_permissions]


class WorkerSearchViewSet(BaseLoggedViewSet):
    authentication_classes = (SuperUserOnly,)

    def list(self, request):
        serializer = WorkerSearchSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        workers = Worker.objects(serializer.validated_data)
        data = ModelWorkerSearchSerializer(workers, many=True).data
        return JsonResponse(data=data)


class VcardExportSuperViewSet(BaseLoggedViewSet):
    """
    Экспорт работников организаций в формат .vcard
    """
    slug = 'hr'
    authentication_classes = (SuperUserOnly,)

    def list(self, request):
        serializer = VCardSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        request_auth = RequestAuth(request)
        if request_auth.is_super():
            provider_id = serializer.validated_data.get('provider')
            if not provider_id:
                raise ValidationError('Не передан id организации')
        else:
            provider_id = request_auth.get_provider_id()

        provider = Provider.objects(id=provider_id).as_pymongo().first()
        workers = Worker.objects(provider__id=provider_id).as_pymongo()
        vcards = []
        errors = []
        for worker in workers:
            try:
                phones = [
                    p for p in worker.get('phones', []) if p.get('number')
                ]
                if not phones and not worker['email']:
                    continue
                vcard = 'BEGIN:VCARD'
                vcard += '\nVERSION:3.0'
                vcard += f'\nFN:{worker["str_name"]}'
                vcard += f'\nN:{worker.get("last_name", "")};' \
                         f'{worker.get("first_name", "")};' \
                         f'{worker.get("patronymic_name", "")}'
                if worker.get("position") and worker["position"].get('name'):
                    vcard += f'\nTITLE:{worker["position"]["name"]}'
                vcard += f'\nORG:{provider["str_name"]}'
                vcard += f'\nURL:{provider.get("site", "")}'
                vcard += \
                    f'\nEMAIL;TYPE=INTERNET;type=WORK:{worker.get("email", "")}'
                vcard += f'\nBDAY:{worker.get("birth_date", "") or ""}'
                vcard += f'\nNOTE:Лицевой счет №{worker["number"]}'
                for phone in phones:
                    if phone.get("code"):
                        vcard += f'\nTEL;type={phone["type"]};type=VOICE:' \
                                 f'+7{phone["code"]}{phone["number"]}'
                    else:
                        vcard += f'\nTEL;type={phone["type"]};type=VOICE:' \
                                 f'{phone["number"]}'
                vcard += '\nEND:VCARD'
                vcards.append(vcard)
            except Exception as error:
                errors.append(f'Account {worker["number"]} have no key {error}')
        resp = HttpResponse(
            '\n\n'.join(vcards).encode(),
            content_type='text/x-vcard',
            charset='utf-8'
        )
        disposition = f'attachment; filename="{provider["str_name"]}"'
        resp['Content-Disposition'] = disposition.encode()
        return resp


class WorkerTimerViewSet(BaseLoggedViewSet):
    authentication_classes = (SuperUserOnly,)

    @permission_validator
    def create(self, request):
        worker = self.get_worker(request)

        if getattr(worker, 'timer', None) and not worker.timer.stopped_at:
            raise ValidationError('Таймер уже в работе')
        worker.timer = WorkerSupportTimer(started_at=datetime.now())
        worker.save()
        data = ModelWorkerSearchSerializer(worker).data
        return JsonResponse(data=data)

    @permission_validator
    def partial_update(self, request, pk):
        pk = PrimaryKeySerializer.get_validated_pk(pk)
        worker = self.get_worker(request)
        if worker.id != pk:
            raise ValidationError(f'аккаунт {pk} не валидный!')
        if not worker.timer and not worker.timer.started_at:
            raise ValidationError('Таймера не сущесвует')
        worker.timer.stop()
        worker.save()
        data = ModelWorkerSearchSerializer(worker).data
        return JsonResponse(data=data)

    @staticmethod
    def get_worker(request):
        request_auth = RequestAuth(request)
        account = request_auth.get_account()
        if not account:
            raise ValidationError('Вы не вошли как пользователь')
        worker = Worker.objects(id=account.id).first()
        if not worker:
            raise ValidationError('Вы не вошли как работник')
        return worker


class DismissedWorkerViewSet(BaseLoggedViewSet):
    slug = 'hr'

    @permission_validator
    def partial_update(self, request, pk):
        serializer = DismissWorkerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pk = PrimaryKeySerializer.get_validated_pk(pk)
        worker = Worker.objects(id=pk).first()
        worker.is_dismiss = serializer.validated_data['is_dismiss']
        if serializer.validated_data['is_dismiss']:
            if not serializer.validated_data.get('dismiss_date'):
                return HttpResponseBadRequest(
                    '"dismiss_date" field is required',
                )
            worker.dismiss_date = serializer.validated_data['dismiss_date']
        else:
            worker.dismiss_date = None
        worker.save()
        Permissions.objects(actor_id=pk).delete()
        data = ModelWorkerSearchSerializer(worker).data
        return JsonResponse(data=data)


class AccessWorkerViewSet(BaseLoggedViewSet):
    slug = 'worker_rules'

    @permission_validator
    def partial_update(self, request, pk):
        serializer = AccessWorkerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pk = PrimaryKeySerializer.get_validated_pk(pk)
        worker = Worker.objects(id=pk).first()
        if not worker:
            raise DoesNotExist()
        has_access = serializer.validated_data['has_access']
        department = None
        if has_access and not worker.email:
            department = Department.objects(pk=worker.department.id).get()
            if not department.settings.access_without_email:
                return HttpResponseForbidden()
        worker.has_access = has_access
        if serializer.validated_data.get('password'):
            if not department:
                department = Department.objects(pk=worker.department.id).get()
            if not department.settings.access_without_email:
                raise CustomValidationError(
                    'ВНИМАНИЕ! Мы не можем нести ответственность за доступ '
                    'к системе третьих лиц для лицевых счетов, у которых '
                    'не указан email',
                )
            worker.password = worker.password_hash(
                qwerty_password(serializer.validated_data['password']),
            )
            if not worker.email and worker.activation_code:
                worker.activation_code = None
                worker.activation_step = None
        worker.save()
        data = ModelWorkerSearchSerializer(worker).data
        return JsonResponse(data=data)


class CopyWorkerPermissionsViewSet(BaseLoggedViewSet):
    slug = 'worker_rules'
    permission_classes = (SuperUserOnly,)

    @permission_validator
    def create(self, request):
        serializer = CopyWorkerPermissionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        parent_worker = serializer.validated_data['parent_worker']
        child_worker = serializer.validated_data['child_worker']
        if Worker.objects(id__in=[parent_worker, child_worker]).count() < 2:
            raise DoesNotExist()
        parent_permission = Permissions.objects(actor_id=parent_worker).first()
        if not parent_permission:
            raise DoesNotExist()
        child_permission = Permissions.objects(actor_id=child_worker).first()
        if child_permission:
            child_permission.current = parent_permission.current
            child_permission.granular = parent_permission.granular
            child_permission.general = parent_permission.general
            child_permission.save()
        else:
            Permissions(
                actor_id=child_worker,
                _id=f"Account:{child_worker}",
                actor_type="Account",
                current=parent_permission.current,
                granular=parent_permission.granular,
                general=parent_permission.general,
            ).save()
        return HttpResponse("Права скопированы")


class WorkerManagementViewSet(BaseLoggedViewSet):
    """Управление пользователем."""
    slug = 'hr'
    permission_classes = (SuperUserOnly,)

    def retrieve(self, request, pk):
        request_auth = RequestAuth(request)
        pk = PrimaryKeySerializer.get_validated_pk(pk)
        worker = Worker.objects(
            Worker.get_binds_query(request_auth.get_binds()),
            id=pk,
        ).get()
        worker = WorkerManagementSerializer(worker).data
        return JsonResponse(data=worker)

    @staticmethod
    def partial_update(request, pk):
        request_auth = RequestAuth(request)
        serializer = WorkerManagementSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            pk = PrimaryKeySerializer.get_validated_pk(pk)
            worker = Worker.objects(
                Worker.get_binds_query(request_auth.get_binds()),
                id=pk,
            ).get()
            worker.update(
                has_access=data['has_access'], is_super=data['is_super']
            )
            return HttpResponse('updated')
        return HttpResponse('invalid data')


class TemplateMessageViewSet(viewsets.ViewSet, SerializationMixin):
    def get_serializer_class(self):
        return MessengerTemplateSerializer

    @action(detail=False, methods=['GET'])
    def get_template_message(self, request, *args, **kwargs):
        worker = self.handle_super_request()
        if not worker.is_super:
            return Response(status=403)
        message = MessengerTemplate.get_or_create(worker_id=worker.id).message
        return JsonResponse(data={'message': message})

    @action(detail=False, methods=['PATCH'])
    def set_template_message(self, request, *args, **kwargs):
        validated_data = self.get_validated_data(request)
        worker = self.handle_super_request()
        if not worker.is_super:
            return Response(status=403)
        message = MessengerTemplate.upsert(
            worker_id=worker.id,
            message=validated_data['message'],
        ).message
        return JsonResponse(data={'message': message})

