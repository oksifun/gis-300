"""Создаёт начальную структуру директорий для новых приложений."""

from django.core.management.base import BaseCommand
from pathlib import Path


class Command(BaseCommand):
    REQUIRED_DIRS = ('models', 'core', 'migrations')
    help = 'Создаёт начальную структуру для нового приложения'
    app_path = None
    path = Path('app/')

    def add_arguments(self, parser):
        parser.add_argument(
            'app_name',
            type=str,
            help='название приложения',
        )
        parser.add_argument(
            '-a',
            '--with-api',
            help='добавить api',
            action='store_true',
        )
        parser.add_argument(
            '-c',
            '--with-celery',
            help='добавить celery',
            action='store_true',
        )

    def handle(self, *args, **options):
        with self:
            app_name = options['app_name']
            if self.path.joinpath(app_name).exists():
                message = "Приложение с именем {} уже существует.".format(app_name)
                raise OSError(message)
            self.app_path = self.create_package(app_name)
            for directory in self.REQUIRED_DIRS:
                self.create_package(directory, self.app_path)
            if options['with_celery']:
                self.with_celery()
            if options['with_api']:
                self.with_api()
            self.stdout.write(self.style.SUCCESS(
                "Приложение с именем {} создано.".format(app_name),
            ))

    def with_celery(self):
        workers_path = self.create_package('workers')
        tasks_path = self.create_package('tasks')
        dict_files = {
            'config.py': [
                'from celery import Celery',
                'from processing.celery.config import CELERY_CONFIG',
            ],
        }
        for filename, content in dict_files.items():
            self.create_file_with_content(
                filename,
                content,
                path=workers_path,
            )

    def with_api(self):
        api_path = self.create_package('api')
        api_version_path = self.create_package('v4', api_path)
        dict_files = {
            'serializers.py': [
                'from rest_framework_mongoengine import serializers',
                'from api.v4.serializers import BaseCustomSerializer',
            ],
            'urls.py': [
                'from rest_framework.routers import DefaultRouter',
            ],
            'views.py': '',
        }
        for filename, content in dict_files.items():
            self.create_file_with_content(
                filename,
                content,
                path=api_version_path,
            )

    def create_package(self, package_name, path=None, exist_ok=False):
        """Создаёт python пакет и возвращает путь к нему."""
        path = path or self.app_path or self.path
        package_path = path.joinpath(package_name)
        Path.mkdir(package_path, exist_ok=exist_ok)
        Path(package_path.joinpath('__init__.py')).touch()
        return package_path

    def create_file_with_content(self, filename, content=('',), path=None):
        """Создаёт файл с содержанием content и возвращает путь к файлу."""
        content = [content] if type(content) is str else content
        content = ("{}\n".format(s) for s in content)
        path = path or self.app_path or self.path
        file_path = path.joinpath(filename)
        with file_path.open('w') as f:
            f.writelines(content)
        return file_path

    def change_permissions(self):
        if self.app_path:
            self.app_path.chmod(0o777)
            _ = [f.chmod(0o777) for f in self.app_path.glob("**/*")]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is None:
            self.change_permissions()
        else:
            self.stdout.write(self.style.ERROR(
                "Ошибка. {}".format(exc_val),
            ))

