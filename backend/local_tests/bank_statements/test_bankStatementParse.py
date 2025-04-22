import os
import warnings
from datetime import datetime
from unittest import TestCase

import django

from api.v4.mixins import ConnectMixin

from bson import ObjectId
from dateutil.parser import parse

from app.bankstatements.tasks.compare import compare_bank_statement
from app.bankstatements.core.parser import BankStatementParse
from processing.models.billing.payment import PaymentDoc
from processing.models.billing.provider.main import Provider
from app.bankstatements.models.parse_task import BankStatement
from app.bankstatements.models.bankstatement_doc import BankStatementDoc
from processing.models.billing.files import Files


class TestBankStatementParse(ConnectMixin, TestCase):
    PROVIDER = ObjectId("526234b3e0e34c4743822066")
    FILE_NAME = 'kl_to_24062019.txt'
    FILE = None

    def clean_db(self):
        query = {
            'date': parse("2019-06-24T00:00:00Z"),
            'provider': ObjectId("526234b3e0e34c4743822066"),
            '_id': {'$gt': ObjectId("5d133b2ccbc69c0014548bb0")}
        }
        PaymentDoc.objects(__raw__=query).delete()
        BankStatementDoc.objects(provider=self.PROVIDER).delete()
        BankStatement.objects(
            provider=self.PROVIDER,
            file__name=self.FILE_NAME
        ).delete()
        query = {
            'date': parse("2019-06-24T00:00:00Z"),
            'provider': ObjectId("526234b3e0e34c4743822066")
        }
        PaymentDoc.objects(__raw__=query).update(
            set__bank_compared=False,
            unset__lock=1,
            unset__bank_statement=1,
        )

    def setUp(self):
        django.setup()
        super().setUp()
        warnings.simplefilter("ignore")
        file_path = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(file_path, self.FILE_NAME), 'rb') as f:
            self.FILE = f.read()
        self.clean_db()

    def tearDown(self):
        warnings.simplefilter("ignore")
        self.clean_db()
        super().tearDown()

    def test_parsing(self):
        warnings.simplefilter("ignore")
        provider = Provider.objects(id=self.PROVIDER).get()
        filename = self.FILE_NAME
        file_body = self.FILE
        bs = BankStatementParse(file_body, filename, provider)

        condition = (
                bs.PF['create_date'] in bs.bank_statement
                and bs.PF['create_time'] in bs.bank_statement
        )
        if condition:
            date_time = parse(
                f"{bs.bank_statement[bs.PF['create_date']]}T"
                f"{bs.bank_statement[bs.PF['create_time']]}"
            )
        else:
            date_time = datetime.now()

        bank_accounts = []
        for bank in bs.bank_accounts:
            ba_dict = {
                'total_sum': float(bank.get(bs.PF['total_sum'], 0)),
                'bank_account': bank[bs.PF['check_acc']],
            }

            if bs.PF['final_balance'] in bank:
                ba_dict['final_balance'] = float(
                    bank.get(bs.PF['final_balance'], 0)
                )
            elif bs.PF['begin_balance'] in bank:
                ba_dict['final_balance'] = float(
                    bank.get(bs.PF['begin_balance'], 0)
                )
            bank_accounts.append(ba_dict)

        bs_file = Files()
        bs_file.save_file(body=file_body, name=filename, owner_id=provider.id)
        # Сохраняем файл выписки.
        bank_statement = BankStatement(
            provider=provider.id,
            file=bs_file,
            datetime=date_time,
            date_from=bs.bank_statement[bs.PF['date_start']],
            date_till=bs.bank_statement[bs.PF['date_end']],
            bank_accounts=bank_accounts,
            state='new'
        )
        bank_statement.save()
        # Создаем таску на сверку выписки
        compare_bank_statement(bs_id=bank_statement.id)
        bank_statement.reload()
        self.assertEqual(bank_statement.state, 'ready')
