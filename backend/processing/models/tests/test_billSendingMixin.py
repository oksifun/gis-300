import datetime
from unittest import TestCase

from bson import ObjectId

from api.v4.mixins import ConnectMixin
from processing.models.billing.account import Tenant, BillSendingEmbedded


class TestBillSendingMixin(ConnectMixin, TestCase):
    TESTER_ACCOUNT = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUp(cls)
        user = {
            "old_numbers": [],
            "photo": None,
            "str_name": "Икакий Тестер Иракиевич",
            "inn": None,
            "comment": None,
            "birth_date": None,
            "last_name": "Икакий",
            "patronymic_name": "Иракиевич",
            "number": "7849777720136",
            "email": "tester@eis24.me",
            "phones": [],
            "short_name": "Тестер И.И.",
            "_type": ["Tenant", "PrivateTenant"],
            "is_super": True,
            "get_access_date": datetime.datetime.now(),
            "_binds": {"hg": [ObjectId()]}
        }
        account_id = Tenant.objects.insert(Tenant(**user), load_bulk=False)
        cls.TESTER_ACCOUNT = account_id

    @classmethod
    def tearDownClass(cls) -> None:
        cls.assertEqual(Tenant._get_db().name, 'test_legacy')
        Tenant.drop_collection()
        super().tearDown(cls)

    def tearDown(self):
        Tenant.objects(id=self.TESTER_ACCOUNT).update_one(unset__b_settings=1)

    def test_find_bill_setting_by_sector(self):
        sector = 'sector_name'
        tenant = self._get_tenant()
        result = tenant.find_bill_settings(sector)
        self.assertIsNone(result)
        tenant.b_settings = [BillSendingEmbedded(
            sector=sector,
            sent=datetime.datetime.now(),
            doc=ObjectId()
        )]
        tenant.save()
        tenant.reload()
        result = tenant.find_bill_settings(sector)
        self.assertEqual(result.sector, sector)

    def test_mark_bill_as_sent(self):
        doc_id = ObjectId()
        sector = 'sector_name'
        tenant = self._get_tenant()
        self.assertEqual(tenant.b_settings, [])
        tenant.set_bill_sent(
            sector=sector, doc_id=doc_id, mailing_type='slip'
        )
        tenant.reload()
        t_settings = tenant.b_settings
        self.assertEqual(len(t_settings), 1)
        self.assertEqual(t_settings[0].sector, sector)
        self.assertEqual(t_settings[0].sector, sector)
        self.assertEqual(t_settings[0].doc, doc_id)
        self.assertIsInstance(t_settings[0].sent, datetime.datetime)

        tenant.set_bill_sent(sector='new_sector', doc_id=doc_id)
        tenant.reload()
        self.assertEqual(len(t_settings), 2)

        last_sent = tenant.b_settings[0].sent
        tenant.set_bill_sent(sector=sector, doc_id=doc_id)
        tenant.reload()
        self.assertGreater(tenant.b_settings[0].sent, last_sent)

    def _get_tenant(self):
        return Tenant.objects(id=self.TESTER_ACCOUNT).get()
