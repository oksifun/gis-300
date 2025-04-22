# -*- coding: utf-8 -*-
from io import BytesIO
from zipfile import ZipFile


class ZipArchive:
    """Возвращает буфер zip-архива с json-файлами экспорта."""
    def __init__(self, json_files: list) -> bytes:
        self.json_files = json_files
    
    def as_bytes(self):
        buffer = BytesIO()
        if not self.json_files:
            return buffer
        with ZipFile(buffer, 'a') as zip_archive:
            for json_file in self.json_files:
                zip_archive.writestr(
                    str(json_file.full_file_path),
                    json_file.content,
                )
        return buffer
