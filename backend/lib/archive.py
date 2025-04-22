from uuid import uuid4

import os
import shutil
import zipfile
import tempfile
from shlex import quote

from gridfs.grid_file import GridOut

from lib.gridfs import get_file_from_gridfs, put_file_to_gridfs
from settings import DEFAULT_TMP_DIR


def extract_7z(file_path, real_filename, password):
    """
    разархивирует переданный файл во временную папку, затем перемещает извлеченные файлы в /tmp/
    и возвращает список кортежей [(полный путь к файлу, ориганальное имя файла,),...]
    """
    output_path = tempfile.mkdtemp()

    exit_code = os.system(
        '7z -p{0} -o{1} -y e {2}'.format(quote(password), quote(output_path), quote(file_path))
    )
    if exit_code != 0:
        raise ValueError('Got error during un-7zipping of %s (%s)' % (file_path, real_filename))

    extracted_files = os.listdir(output_path)
    result = []
    for f in extracted_files:
        source = '%s/%s' % (output_path, f)
        destination = '/tmp/%s' % f
        shutil.move(source, destination)
        result.append([destination, f])
    return result


def extract_zip(file_path):
    dest_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(file_path) as zf:
        zf.extractall(dest_dir)

    files = []
    for f in os.listdir(dest_dir):
        files.append(os.path.join(dest_dir, f))
    return files


def get_files_from_zip(file, password=None):
    zf = zipfile.ZipFile(file)
    names = zf.namelist()
    files = []
    for name in names:
        files.append({
            'filename': name,
            'file': zf.read(name, pwd=password),
        })
    return files


def get_file_from_zip(arch_path, file_name, src_dir):
    zf = zipfile.ZipFile(arch_path)
    data = zf.read(file_name)
    file_path = os.path.join(src_dir, file_name)
    with open(file_path, 'wb') as f:
        f.write(data)
    return file_path


def create_zip(files, name, dst=None, compress=True):
    if not dst:
        dst = DEFAULT_TMP_DIR

    # Имя файла может быть максимум 255 байт, обрезаем имя пока не будет 250 байт
    while dst.__sizeof__() + name.__sizeof__() > 250:
        name = name[:-1]

    # Изменяет слэш в имени во избежании конфликта
    name = name.replace('/', '_')
    # Проверка расшрения файла
    if not name.endswith('.zip'):
        name += '.zip'

    zf = zipfile.ZipFile(
        os.path.join(dst, name),
        'w',
        compression=zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED,
    )
    for f in files:
        if isinstance(f, GridOut):
            f_bytes = f.read()
            file_name = f.filename.replace('/', '_')
            if len(file_name) >= 252:
                file_name = file_name[0: 40] + '...' + file_name[-200:]
            path = '{}/{}'.format(dst, uuid4().hex)
            with open(path, 'wb') as tmp_file:
                tmp_file.write(f_bytes)
                tmp_file.close()
            zf.write(path, file_name)
        else:
            zf.write(f, os.path.split(f)[-1])
    zf.close()
    return zf.filename


def create_zip_no_tmp(gs_files, name, dst=None, compress=True):
    if not dst:
        dst = DEFAULT_TMP_DIR
    while dst.__sizeof__() + name.__sizeof__() > 250:
        name = name[:-1]
    name = name.replace('/', '_')
    if not name.endswith('.zip'):
        name += '.zip'
    zf = zipfile.ZipFile(
        os.path.join(dst, name),
        'w',
        compression=zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED,
    )
    for f in gs_files:
        f_bytes = f.read()
        file_name = f.filename.replace('/', '_')
        if len(file_name) >= 252:
            file_name = file_name[0: 40] + '...' + file_name[-200:]
        zf.writestr(file_name, f_bytes)
    zf.close()
    return zf.filename


def create_zip_file_in_gs(filename, resource_name, resource_id,
                          file_paths=None, gs_ids=None, id_return=False,
                          no_tmp=False):
    assert file_paths or gs_ids
    if gs_ids:
        files = []
        for gs_id in gs_ids:
            f = get_file_from_gridfs(gs_id, raw=True)
            if f:
                files.append(f)
        if no_tmp:
            zip_path = create_zip_no_tmp(files, filename)
        else:
            zip_path = create_zip(files, filename)
    else:
        zip_path = create_zip(file_paths, filename)
    with open(zip_path, 'rb') as f:
        lines = f.read()
        uuid = uuid4().hex
        file_id = put_file_to_gridfs(
            resource_name, resource_id, lines, uuid=uuid,
            filename='{}.{}'.format(filename, 'zip'),
        )
        f.close()
        return (uuid, file_id) if id_return else uuid

