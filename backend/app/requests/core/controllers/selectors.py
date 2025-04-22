from typing import (
    Union,
    Optional,
)

from bson import ObjectId
from mongoengine import (
    DoesNotExist,
    QuerySet,
)

from app.requests.models.request import Request
from processing.models.billing.base import BindsPermissions


class RequestSelector:

    @staticmethod
    def get_object(
            pk: ObjectId,
            binds: Union[BindsPermissions, dict],
    ) -> Optional[Request]:
        try:
            obj = Request.objects(
                Request.get_binds_query(binds),
                is_deleted__ne=True,
                pk=pk,
            ).get()
        except DoesNotExist:
            return None
        return obj

    @staticmethod
    def get_queryset(
            binds: Union[BindsPermissions, dict],
    ) -> Optional[QuerySet]:
        obj = Request.objects(
            Request.get_binds_query(binds),
            is_deleted__ne=True,
        ).all()
        return obj
