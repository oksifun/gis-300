# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from importlib import import_module
from inspect import isclass
from pathlib import Path


class AbstractDiscovery(ABC):
    """Абстрактный класс для автодискавери."""

    @property
    @abstractmethod
    def globs_list(self):
        """Список шаблонов поиска файлов."""
        pass

    @property
    @abstractmethod
    def subclass(self):
        """Тип классов, которые мы хотим получить."""
        pass
    
    @abstractmethod
    def filter_classes(self, classes, *args, **kwargs):
        """Функция-фильтр по отбору нужных классов."""
        pass

    def __call__(self, *args, **kwargs):
        return self.__find_classes(*args, **kwargs)
    
    def __find_classes(self, *args, **kwargs):
        """Возвращает список классов отфильтрованных по relation_with."""
        model_paths = self.__get_files()
        module_attributes = map(
            lambda x: (getattr(x, attribute_name) for attribute_name in dir(x)),
            map(import_module, map(self.__normalize_module_name, model_paths))
        )
        attributes = (attribute for module_attribute in module_attributes
                      for attribute in module_attribute)
        classes = filter(
            lambda x: isclass(x) and issubclass(x, self.subclass), attributes)
        return self.filter_classes(classes, *args, **kwargs)

    def __get_files(self):
        """Список файлов из директорий glob_list."""
        files = []
        path = Path('.')
        for glob in self.globs_list:
            files.extend(
                [file for file in path.glob(glob)
                 if not file.name.startswith('__')])
        return files
    
    @staticmethod
    def __normalize_module_name(model_path):
        """Преобразовывает путь к файлу в путь к модулю."""
        return '.'.join(model_path.parts).replace('.py', '')
