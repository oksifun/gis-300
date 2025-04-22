# -*- coding: utf-8 -*-
from processing.models.billing.provider.main import Provider
from mongoengine import signals


signals.post_save.connect(Provider.post_save, sender=Provider)



