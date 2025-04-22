from unittest import TestCase

from app.offsets.core.calculator.timeline import Timeline
from app.offsets.core.calculator.operation import Record
from app.offsets.core.calculator.utils import money
from datetime import datetime


class CalculatorTestCase(TestCase):
    def setUp(self):
        self.timeline = Timeline(provider=None, account=None)
        self.timeline.records = [
            Record(
                date=datetime.strptime("2016-01-01", "%Y-%m-%d"),
                target_date=datetime.strptime("2016-01-01", "%Y-%m-%d"),
                value=money('100'),
                service_type=None
            ),
            Record(
                date=datetime.strptime("2016-02-01", "%Y-%m-%d"),
                target_date=datetime.strptime("2016-02-01", "%Y-%m-%d"),
                value=money('200'),
                service_type=None
            ),
            Record(
                date=datetime.strptime("2016-02-05", "%Y-%m-%d"),
                target_date=datetime.strptime("2016-02-01", "%Y-%m-%d"),
                value=money('-100'),
                service_type=None
            ),
            Record(
                date=datetime.strptime("2016-02-20", "%Y-%m-%d"),
                target_date=datetime.strptime("2016-03-01", "%Y-%m-%d"),
                value=money('-100'),
                service_type=None
            ),
            Record(
                date=datetime.strptime("2016-03-1", "%Y-%m-%d"),
                target_date=datetime.strptime("2016-03-01", "%Y-%m-%d"),
                value=money('100'),
                service_type=None
            ),
            Record(
                is_penalty=True,
                date=datetime.strptime("2016-03-01", "%Y-%m-%d"),
                target_date=datetime.strptime("2016-03-01", "%Y-%m-%d"),
                value=money('10'),
                service_type=None
            ),
            Record(
                date=datetime.strptime("2016-03-30", "%Y-%m-%d"),
                target_date=datetime.strptime("2016-03-01", "%Y-%m-%d"),
                value=money('-110'),
                service_type=None
            ),
            Record(
                date=datetime.strptime("2016-04-01", "%Y-%m-%d"),
                target_date=datetime.strptime("2016-04-01", "%Y-%m-%d"),
                value=money('150'),
                service_type=None
            ),
            Record(
                is_penalty=True,
                date=datetime.strptime("2016-04-01", "%Y-%m-%d"),
                target_date=datetime.strptime("2016-04-01", "%Y-%m-%d"),
                value=money('20'),
                service_type=None
            ),
            Record(
                date=datetime.strptime("2016-04-05", "%Y-%m-%d"),
                target_date=datetime.strptime("2016-02-01", "%Y-%m-%d"),
                value=money('-200'),
                service_type=None
            ),
            Record(
                date=datetime.strptime("2016-04-10", "%Y-%m-%d"),
                target_date=datetime.strptime("2016-04-01", "%Y-%m-%d"),
                value=money('-100'),
                service_type=None
            ),
            Record(
                date=datetime.strptime("2016-05-01", "%Y-%m-%d"),
                target_date=datetime.strptime("2015-05-01", "%Y-%m-%d"),

                value=money('100'),
                service_type=None
            ),
        ]
        for record in self.timeline.records:
            record.update_cache()

        self.timeline.link_all()

    def testComplex(self):
        self.assertEqual(len(self.timeline.links), 9)

        self.assertEqual(self.timeline.links[0].value, 100)
        self.assertEqual(self.timeline.links[0].credit, self.timeline.records[2])
        self.assertEqual(self.timeline.links[0].debit, self.timeline.records[1])

        self.assertEqual(self.timeline.links[1].value, 100)
        self.assertEqual(self.timeline.links[1].credit, self.timeline.records[3])
        self.assertEqual(self.timeline.links[1].debit, self.timeline.records[0])

        self.assertEqual(self.timeline.links[2].value, 100)
        self.assertEqual(self.timeline.links[2].credit, self.timeline.records[6])
        self.assertEqual(self.timeline.links[2].debit, self.timeline.records[4])

        self.assertEqual(self.timeline.links[3].value, 10)
        self.assertEqual(self.timeline.links[3].credit, self.timeline.records[6])
        self.assertEqual(self.timeline.links[3].debit, self.timeline.records[5])

        self.assertEqual(self.timeline.links[4].value, 100)
        self.assertEqual(self.timeline.links[4].credit, self.timeline.records[9])
        self.assertEqual(self.timeline.links[4].debit, self.timeline.records[1])

        self.assertEqual(self.timeline.links[5].value, 100)
        self.assertEqual(self.timeline.links[5].credit, self.timeline.records[9])
        self.assertEqual(self.timeline.links[5].debit, self.timeline.records[7])

        self.assertEqual(self.timeline.links[6].value, 50)
        self.assertEqual(self.timeline.links[6].credit, self.timeline.records[10])
        self.assertEqual(self.timeline.links[6].debit, self.timeline.records[7])

        self.assertEqual(self.timeline.links[7].value, 20)
        self.assertEqual(self.timeline.links[7].credit, self.timeline.records[10])
        self.assertEqual(self.timeline.links[7].debit, self.timeline.records[8])

        self.assertEqual(self.timeline.links[8].value, 30)
        self.assertEqual(self.timeline.links[8].credit, self.timeline.records[10])
        self.assertEqual(self.timeline.links[8].debit, self.timeline.records[11])


class SerializerTestCase(TestCase):
    pass
