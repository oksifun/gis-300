
from processing.models.tasks.base import Task


def all_subclasses(cls):
    return cls.__subclasses__() + [g for s in cls.__subclasses__() for g in all_subclasses(s)]


for subclass in all_subclasses(Task):
    print(subclass._class_name, ',',getattr(subclass, 'DESCRIPTION', ''))

