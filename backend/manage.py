#!/usr/bin/env python
import sys

import os
from django.core.management import execute_from_command_line

from mongoengine_connections import register_mongoengine_connections

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault("SETTINGS_FILE", "local.yml")
    register_mongoengine_connections()
    execute_from_command_line(sys.argv)
