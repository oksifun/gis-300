# -*- coding: utf-8 -*-
import datetime

from mongoengine import (StringField, BooleanField, DateTimeField,
                         EmbeddedDocumentField, ListField)

from app.auth.models.embeddeds import SlaveEmbedded


class ActorsMixin:

    def become_the_master(self, session_id):
        """Возвращение к мастер сессии, путем удаление ссылки на раба"""
        for session in getattr(self, 'sessions'):
            if session.id == session_id:
                from app.auth.models.sessions import Session
                session_ins = Session.objects(
                    pk=session_id,
                ).get()
                session_ins.slave = None
                session_ins.save()
                session.slave = None
                getattr(self, 'save')()
                return True
        return False


class SessionDataMixin:
    uuid = StringField()
    created = DateTimeField(required=True, default=datetime.datetime.now)
    active = BooleanField(required=True, default=True)
    slave = EmbeddedDocumentField(
        SlaveEmbedded, verbose_name='Внешнее управление')
    remote_ip = StringField()
    screen_sizes = ListField(StringField())
