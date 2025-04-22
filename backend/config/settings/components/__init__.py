# -*- coding: utf-8 -*-
from pathlib import PurePath

from decouple import AutoConfig


BASE_DIR = PurePath(__file__).parent.parent.parent.parent
config = AutoConfig(search_path=BASE_DIR)
