from io import BytesIO
from zipfile import ZipFile


class InMemoryFile:

    def __init__(self, initial_bytes=b''):
        self.memfile = BytesIO(initial_bytes)

    def __getattr__(self, item):
        return getattr(self.memfile, item)


class InMemoryZipFile(InMemoryFile):

    def add_file(self, inzip_filename, data):
        zip_file = ZipFile(self.memfile, 'a')
        zip_file.writestr(inzip_filename, data)
        zip_file.close()

