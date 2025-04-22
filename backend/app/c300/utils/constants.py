from typing import Any


def enum_to_constants(enum: Any,
                      value: str = 'name',
                      text: str = 'value',
                      **kwargs,
                      ):
    """Преобразовывает enum к принятым на проекте константам."""
    return [
        {
            'value': getattr(item, value),
            'text': getattr(item, text),
            **{k: getattr(item, v) for k, v in kwargs.items()},
        } for item in enum]
