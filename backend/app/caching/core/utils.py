_SUFFIXES = ['Н', 'П', '']


def parse_str_number_list(number_list, max_number=10000):
    """
    Парсинг строки со списком номеров квартир/подъездов.
    Допускает использование диапозонов.
        '1,2,3,4,5-20,60-67,80П,81Н,90-95П,100-120Н'
    """
    numbers = set()

    try:
        for chunk in number_list.replace(' ', '').split(','):
            if '-' in chunk:
                low_high = chunk.split('-')
                str_numbers = check_str_number(low_high)
                if len(low_high) != 2 or not str_numbers:
                    raise ValueError('Неверный формат списка номеров')
                low, high = int(str_numbers[0][0]), int(str_numbers[1][0]) + 1
                letter = str_numbers[0][1]
                if high > max_number:
                    raise ValueError(
                        f'Превышен максимальный номер: {high}, max={max_number}'
                    )
                numbers |= set([f'{i}{letter}' for i in range(low, high)])
                numbers |= set([f'{i}-{letter}' for i in range(low, high)])
            else:
                numbers.add(chunk)
    except (IndexError, ValueError):
        raise ValueError('Неверный формат списка номеров')

    return list(numbers)


def parse_number_list(number_list, max_number=10000):
    """
    Парсинг строки со списком номеров квартир/подъездов.
    Допускает использование диапозонов.
        '1,2,3,4,5-20,60-67'
    """
    numbers = set()

    try:
        for chunk in number_list.replace(' ', '').split(','):
            if '-' in chunk:
                low_high = chunk.split('-')

                if len(low_high) != 2:
                    raise ValueError('Неверный формат списка номеров')

                low, high = int(low_high[0]), int(low_high[1]) + 1
                if high > max_number:
                    raise ValueError(
                        'Превышен максимальный номер: {}, max={}'.format(
                            high,
                            max_number,
                        ),
                    )
                numbers |= set(range(low, high))
            else:
                numbers.add(int(chunk))
    except (IndexError, ValueError):
        raise ValueError('Неверный формат списка номеров')

    return list(numbers)


def check_str_number(str_numbers):
    check_numbers = []

    for str_number in str_numbers:
        int_number = ''.join([i for i in str_number if i.isdigit()])
        alpha_number = ''.join([i for i in str_number if i.isalpha()])
        if alpha_number not in _SUFFIXES or not int_number:
            return
        else:
            check_numbers.append([int_number, alpha_number])
            if check_numbers[0][1] != check_numbers[-1][1]:
                return
    return check_numbers
