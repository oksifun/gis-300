from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse

from jinja2 import Environment


def environment(**options):
    env = Environment(**options)
    env.globals.update({
        'staticfiles': staticfiles_storage.url,
        'reverse': reverse,
    })
    return env
