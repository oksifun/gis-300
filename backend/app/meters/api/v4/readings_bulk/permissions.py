from bson import ObjectId
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from api.v4.authentication import RequestAuth


class WhiteListProvider(BasePermission):
    """
    Класс для проверки доступа провайдеров

    """

    white_list_providers = [
        ObjectId("62ce80476470f300171a2a2c"),
        ObjectId("5bfe8c9cbdb48e0031d40e10"),
    ]

    def has_permission(self, request: Request, view: APIView) -> bool:
        auth = RequestAuth(request)
        return auth.get_provider_id() in self.white_list_providers

