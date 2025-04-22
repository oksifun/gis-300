from re import match


def is_ogrn(ogrn: str or int) -> bool:
    """
    Корректное значение реквизита ОГРН организации?

    ЮЛ: последняя цифра = остаток от деления числа без последней цифры на 11
    ИП: последняя цифра = остаток от деления числа без последней цифры на 13
    """
    if not ogrn:  # '', 0, None
        return False

    try:
        ogrn = int(ogrn)  # WARN strip
    except (ValueError, TypeError):  # None - TypeError
        return False

    ogrn_length: int = len(str(ogrn))  # только цифры

    if ogrn_length == 13:  # ЮЛ
        return (ogrn // 10 % 11) % 10 == ogrn % 10  # WARN 10 заменяем на 0
    elif ogrn_length == 15:  # ИП
        return (ogrn // 10 % 13) % 10 == ogrn % 10  # WARN 10 заменяем на 0
    else:  # неверное количество цифр в номере!
        return False

def ogrn_or_not(value: str or int) -> str:
    """
    Значение реквизита ОГРН организации
    """
    if not value:  # '', 0, None
        return ''

    found = match(r'^\D*(\d{15}|\d{13})\D*$', str(value))
    return found.group(1) if found else ''

def kpp_or_not(value: str) -> str:
    """
    Значение реквизита КПП организации
    """
    if not value:  # '', 0, None
        return ''

    found = match(r'^\D*(\d{4}[\dA-Z][\dA-Z]\d{3})\D*$', str(value))
    return found.group(1) if found else ''
