from datetime import datetime

from mongoengine import DoesNotExist

from app.notifications.models.notify_data import Notifications
from lib.gridfs import get_file_from_gridfs
from processing.data_producers.public.base import ProviderPublicDataGet
from app.personnel.models.personnel import Worker
from app.news.models.news import News
from processing.models.billing.provider_public import ProviderPublicData

from processing.models.exceptions import CustomValidationError


class OrganizationFilesPublicData(ProviderPublicDataGet):
    DATA_TYPE_DESCRIPTION = 'files'

    def get_file(self, data_type, file_uuid):
        try:
            data = ProviderPublicData.objects.get(
                data_type=data_type,
                provider=self.provider.pk,
            )
        except DoesNotExist:
            return None
        file = get_file_from_gridfs(
            file_id=None,
            uuid=file_uuid,
            raw=True,
        )
        if (
            file._file['owner_resource'] == data._type[0] and
            file._file['owner_id'] == data.pk
        ):
            return file
        if (
            file._file['owner_resource'] == 'Worker' and
            data._type[0] == 'ManagementPublicData' and
            data.data['enabled'] and
            file._file['owner_id'] in data.data['workers']
        ):
            try:
                Worker.objects(
                    pk=file._file['owner_id'],
                    provider__id=self.provider.pk,
                ).as_pymongo().get()
            except DoesNotExist:
                return None
            return file
        if (
            file._file['owner_resource'] == 'News' and
            data._type[0] == 'NewsPublicData' and
            data.data['enabled']
        ):
            try:
                News.objects(
                    pk=file._file['owner_id'],
                    author__provider=self.provider.pk,
                ).as_pymongo().get()
            except DoesNotExist:
                return None
            return file
        return None


class TokenBillFilePublicData:

    def __init__(self, tenant_id, token, source=None):
        self.tenant_id = tenant_id
        self.token = token
        self.source = source

    def get_file(self):
        try:
            notifications = Notifications.objects.get(
                tenant_id=self.tenant_id,
                bills__download_token=self.token
            )
        except DoesNotExist:
            return None
        bill = notifications.find_bill_settings_by_file(self.token)
        if bill.token_lifetime >= datetime.now():
            file = get_file_from_gridfs(
                file_id=bill.download_token,
                uuid=None,
                raw=True,
            )
            notifications.set_bill_downloaded(bill, self.source)
            return file
        else:
            raise CustomValidationError('Срок скачивания квитанции истек')
