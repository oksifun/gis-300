from enum import Enum

import pytest

from app.c300.utils.constants import enum_to_constants


class Category(Enum):
    _141 = 'Споры, связанные с самовольной постройкой'
    _116 = 'Споры с управляющими компаниями'


class DocumentTypes(Enum):
    """Список типов документов и их функции-заполнители."""
    debt_letter = ('Письмо о задолженности',)
    debt_notice = ('Уведомление о задолженности', ('22', '33'))

    def __init__(self, title, tags=None):
        self.title = title
        self.tags = tags or tuple()


test_data_for_enum_to_constants = (
        (Category, {}, [
            {'value': '_141',
             'text': 'Споры, связанные с самовольной постройкой',
             },
            {'value': '_116',
             'text': 'Споры с управляющими компаниями',
             }
        ]),
        (DocumentTypes, {'text': 'title', 'tags': 'tags'}, [
            {'value': 'debt_letter',
             'text': 'Письмо о задолженности',
             'tags': tuple(),
             },
            {'value': 'debt_notice',
             'text': 'Уведомление о задолженности',
             'tags': ('22', '33'),
             }
        ]),
)

@pytest.mark.parametrize(
    'enum, kwargs, result',
    test_data_for_enum_to_constants,
)
def test_enum_to_constants(enum, result, kwargs):
    assert enum_to_constants(enum, **kwargs) == result
