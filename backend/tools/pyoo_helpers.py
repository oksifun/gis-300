import time
import traceback
from functools import wraps
from logging import warning

ZERO_LETTER = 'A'
MAX_LETTER = 'Z'

# TODO вынести хардкод в настройки?
MAX_COLUMNS = 50  # максимум обрабатываемых столбцов с каждого листа
ROW_PARSE_STEP = 500  # сколько строк загружается с листа за раз


def column_letter_to_number(column_letters):
    column_no = -1  # поскольку нумерация рядов начинается с 0, и вместо 'return column - 1, row'
    column_word_position = 0
    for ch in column_letters:
        letters_range = ord(MAX_LETTER) - ord(ZERO_LETTER) + 1
        # номер колонки = (27 ** разряд_буквы) * значение_буквы
        # где:
        #   - номер колонки начинается с 0
        #   - разряд_буквы отсчитывается с правой буквы и начинается с 0
        #   - значение буквы от 0 до 26, где A == 0, а Z == 26
        column_no += letters_range ** (len(column_letters) - column_word_position - 1) * (ord(ch) - ord(ZERO_LETTER) + 1)

        column_word_position += 1

    return column_no


def cell_address_to_coordinates(address: str):

    address = address.upper()

    letters, digits = [], []

    # собираем все буквенные символы в начале строки из диапазона от A до Z
    ch_pos = 0
    while ch_pos < len(address) and address[ch_pos].isalpha() and ord(ZERO_LETTER) <= ord(address[ch_pos]) <= ord(MAX_LETTER):
        letters.append(address[ch_pos])
        ch_pos += 1

    # собираем все числовые символы, находящиеся после буквенных, до конца строки или до нечислового символа
    while ch_pos < len(address) and address[ch_pos].isdigit():
        digits.append(address[ch_pos])
        ch_pos += 1

    # Должна быть хотя бы одна буква и одна цифра
    if not letters or not digits:
        raise ValueError('Invalid cell address: {}'.format(address))

    column = column_letter_to_number(letters)

    row = int(''.join(digits)) - 1

    return column, row


def retry(exceptions, delay=1, tries=4):
    def deco_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries = tries
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except exceptions as exc:
                    warning(
                        'Retry({} remain) {}: {}'.format(
                            mtries - 1,
                            f.__name__,
                            traceback.format_exc()
                        )
                    )
                    time.sleep(delay)
                    mtries -= 1
            return f(*args, **kwargs)
        return f_retry
    return deco_retry


if __name__ == '__main__':
    # # TODO переделать в тесты
    #
    # print(cell_address_to_coordinates('A1'))
    # print(cell_address_to_coordinates('Z2'))
    # print(cell_address_to_coordinates('AA3'))
    # print(cell_address_to_coordinates('ZK34'))
    #
    # print(column_letter_to_number('A'))
    # print(column_letter_to_number('C'))
    # print(column_letter_to_number('Z'))
    # print(column_letter_to_number('AA'))

    import random

    @retry(Exception, tries=4)
    def fail(text):
        if random.random() > 0.5:
            raise Exception("Fail")
        else:
            print(text)


    fail("it works!")

