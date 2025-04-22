from unittest import TestCase

from app.offsets.core.calculator.utils import split_mandates_proportionally, money


class UtilsTestCase(TestCase):
    def setUp(self):
        self.money_matrix = [
            [
                money('0'),
                [money('1'), money('1'), money('1')],
                [money('0'), money('0'), money('0')]
            ],
            [
                money('3613.5'),
                [
                    money('10.03'), money('44.75'), money('358.61'), money('192.37'), money('48.85'),
                    money('41.27'), money('15.52'), money('26.50'), money('69.67'), money('4.16'),
                    money('23.09'), money('3.40'), money('146.70'), money('7.95'), money('293.40'),
                    money('146.70'), money('825.45'), money('7.95'), money('44.73'), money('1067.30'),
                    money('92.35'), money('25.36'), money('106.03'), money('11.36')
                ],
                [
                    money('10.03'), money('44.75'), money('358.61'), money('192.37'), money('48.85'),
                    money('41.27'), money('15.52'), money('26.50'), money('69.67'), money('4.16'),
                    money('23.09'), money('3.40'), money('146.70'), money('7.95'), money('293.40'),
                    money('146.70'), money('825.45'), money('7.95'), money('44.73'), money('1067.30'),
                    money('92.35'), money('25.36'), money('106.03'), money('11.36')
                ]
            ],
            [
                money('50'),
                [money('30'), money('26'), money('4')],
                [money('25.01'), money('21.66'), money('3.33')]
            ],
            [
                money('100'),
                [money('30'), money('26'), money('4')],
                [money('30'), money('26'), money('4')]
            ],
            [
                money('14.13'),
                [money('30.26'), money('26.15'), money('44.57')],
                [money('4.25'), money('3.65'), money('6.23')]
            ],
        ]

    def test_split_mandates_proportionally(self):

        for row in self.money_matrix:
            self.assertEqual(split_mandates_proportionally(mandates=row[0], votes=row[1]), row[2])
