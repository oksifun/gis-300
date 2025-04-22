from bson import ObjectId
from django.http import HttpResponse
from mongoengine import ValidationError
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from api.v4.authentication import RequestAuth
from api.v4.base_crud_filters import LimitFilterBackend
from api.v4.forms.base import ConstantsBaseViewSet
from api.v4.forms.tenant import BaseTenantInfoViewSet
from api.v4.universal_crud import BaseCrudViewSet, ModelFilesViewSet
from app.tickets.api.v4.filters import CustomFilter, CustomParamsFilter
from app.tickets.api.v4.serializers import (
    SupportTicketCommentsSerializer,
    SupportTicketCreateSerializer,
    SupportTicketListSerializer,
    SupportTicketNotAuthListSerializer,
    SupportTicketNotAuthSerializer,
    SupportTicketSerializer,
    SupportTicketUpdateSerializer,
    TicketCommentSerializer,
)
from app.tickets.models.support import SupportTicket
from app.tickets.models.tenants import Ticket
from processing.data_producers.forms.tenant_info import (
    get_tenant_tickets_statistic,
)
from processing.models.choices import (
    PHONE_TYPE_CHOICES,
    SUPPORT_TICKET_STATUS_CHOICES,
    SUPPORT_TICKET_TYPE_CHOICES,
    TICKET_ACCESS_LEVEL,
    TICKET_SUBJECT_CHOICES,
    PhoneType,
    SupportTicketStatus,
    TicketAccessLevelCode,
    TicketSubject,
    TicketType
)


class SupportTicketViewSet(BaseCrudViewSet):
    http_method_names = ["get", "post", "patch", "delete"]
    serializer_classes = {
        "create": SupportTicketCreateSerializer,
        "retrieve": SupportTicketSerializer,
        "list": SupportTicketListSerializer,
        "partial_update": SupportTicketUpdateSerializer,
    }
    filter_backends = (
        LimitFilterBackend,
        CustomParamsFilter,
        CustomFilter,
    )

    def get_serializer_class(self):
        request_auth = RequestAuth(self.request)
        if not request_auth.is_super():
            if self.action == "list":
                return SupportTicketNotAuthListSerializer
            if self.action == "retrieve":
                return SupportTicketNotAuthSerializer
        return self.serializer_classes[self.action]

    def get_queryset(self, *args, **kwargs):
        request_auth = RequestAuth(self.request)
        binds = request_auth.get_binds()
        return SupportTicket.objects(
            SupportTicket.get_binds_query(binds), ).order_by(
            "-initial.created_at",
        )

    def create(self, request, *args, **kwargs):
        request_auth = RequestAuth(request)
        account = request_auth.get_account_anyway()
        request.data["initial"] = dict(
            id=ObjectId(),
            body=request.data["initial"]["body"],
            author=account.id,
        )
        request.data["created_by"] = dict(
            id=account.id,
        )
        return super().create(request, *args, **kwargs)


class SupportTicketCommentViewSet(SupportTicketViewSet):
    serializer_class = SupportTicketCommentsSerializer
    model = SupportTicket

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, *args, **kwargs):
        """Получение списка комментариев или создание нового"""
        ignore_filter = False

        if request.method == "POST":
            request.data["files"] = []
            ignore_filter = True

        try:
            comments = self.operate_list_objects(
                request=request,
                object_name="comments",
                object_serializer=TicketCommentSerializer,
            )
            data = self.model.filter_comments(comments.data, request,
                                              ignore_filter)
            return Response(data=data)
        except ValidationError as e:
            return Response(e.message, status=status.HTTP_423_LOCKED)

    @action(
        detail=True,
        methods=["get", "patch", "delete"],
        url_path="comments/(?P<comment_id>\w+)",
    )
    def comment(self, request, comment_id, *args, **kwargs):
        """Работа с одним комментарием (получение/удаление/редактирование)"""
        try:
            comment = self.operate_one_object(
                request=request,
                object_id=comment_id,
                object_name="comments",
                object_serializer=TicketCommentSerializer,
            )
            if request.method == "DELETE":
                return Response(data=comment_id)
            data = self.model.filter_comments([comment.data], request)
            return Response(data=data)
        except ValidationError as e:
            return Response(e.message, status=status.HTTP_423_LOCKED)


class SupportTicketFilesViewSet(ModelFilesViewSet):
    model = SupportTicket

    @action(detail=True, methods=["patch"],
            url_path="comments/(?P<comment_id>\w+)")
    def comment(self, request, comment_id, *args, **kwargs):
        """Работа с одним комментарием (получение/удаление)"""
        ticket_id = kwargs["pk"]
        request_auth = RequestAuth(request)
        current_provider = request_auth.get_provider()
        queryset = self.model.objects(
            pk=ticket_id,
            comments__id=comment_id,
        )
        obj = queryset.get()
        self.put_file(
            request,
            obj,
            queryset,
            current_provider.pk,
            sub_object_field_name="comments",
        )
        return HttpResponse("success")


class TicketFilesViewSet(ModelFilesViewSet):
    model = Ticket
    slug = "tickets"


class SupportTicketConstantsViewSet(ConstantsBaseViewSet):
    CONSTANTS_CHOICES = (
        (TICKET_ACCESS_LEVEL, TicketAccessLevelCode),
        (SUPPORT_TICKET_STATUS_CHOICES, SupportTicketStatus),
        (SUPPORT_TICKET_TYPE_CHOICES, TicketType),
        (PHONE_TYPE_CHOICES, PhoneType),
        (TICKET_SUBJECT_CHOICES, TicketSubject),
    )


class TenantTicketsInfoViewSet(BaseTenantInfoViewSet):
    slag = "tickets"

    @staticmethod
    def make_query(*args, **kwargs):
        return get_tenant_tickets_statistic(*args, **kwargs)
