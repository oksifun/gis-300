from io import BytesIO
from zipfile import ZipFile


class ZipArchive:
    """Возвращает буфер zip-архива."""

    def as_bytes(self, files=None):
        buffer = BytesIO()
        if not files:
            return buffer
        with ZipFile(buffer, 'a') as zip_archive:
            for name_and_stream in files:
                zip_archive.writestr(*name_and_stream)
        return buffer
