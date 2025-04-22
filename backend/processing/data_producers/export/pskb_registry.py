from lib.gridfs import get_file_from_gridfs


class RegistryFormatError(Exception):
    pass


def get_pskb_registry(source_file_id, bank_account):
    # открываем файл
    file = get_file_from_gridfs(source_file_id, raw=True)
    file_bytes = file.read()
    lines = file_bytes.decode('cp1251').split('\r\n')
    # меняем код услуги на расчётный счёт
    reg_format_100500 = False
    for ix, l in enumerate(lines):
        if not l:
            continue
        if l.find('#') == 0:
            reg_format_100500 = True
            if l.find('#SERVICE') == 0:
                lines[ix] = '#SERVICE {}'.format(bank_account)
                break
    if not reg_format_100500:
        raise RegistryFormatError('Format 100500 needed')
    # кодируем обратно в файл и отдаём
    reg_str = '\r\n'.join(lines)
    return file.filename, reg_str.encode('cp1251')
