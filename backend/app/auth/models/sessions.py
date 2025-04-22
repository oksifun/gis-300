# -*- coding: utf-8 -*-
import datetime
from uuid import uuid4

from bson import ObjectId
from mongoengine import Document, ObjectIdField, signals

from app.auth.models.mixins import SessionDataMixin
from processing.models.billing.session import Session as LegacySession
from processing.models.billing.session import SessionEmbeddedAccount


class Session(SessionDataMixin, Document):
    meta = {
        'db_alias': 'auth-db',
        'collection': 'sessions',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'uuid',
            'owner',
        ],
    }
    owner = ObjectIdField(required=True)

    @staticmethod
    def generate_uuid():
        return uuid4().hex
    
    @classmethod
    def create_or_update_in_v2_format(cls, sender, document, **kwargs):
        """Возвращает сессию в формате для api v2."""
        from app.auth.models.actors import Actor, RoboActor
        session_id = str(document.id)
        actor = Actor.objects.get(id=document.owner)
        session_data = {
            'created_at': document.created,
            'is_active': document.active,
            'remote_ip': document.remote_ip,
            'screen_sizes': document.screen_sizes,
            'account': SessionEmbeddedAccount(
                id=actor.owner.id,
                _type=[actor.owner.owner_type],
                is_super=actor.is_super,
                provider={
                    '_id': actor.provider.id,
                }
            )
        }
        if document.slave:
            session_data['slave'] = {
                '_id': str(ObjectId()),
                'created_at': datetime.datetime.now(),
            }
            if document.slave._type == 'Actor':
                actor = Actor.objects.get(id=document.slave.id)
                session_data['slave']['account'] = actor.owner.id
            else:
                actor = RoboActor.objects.get(id=document.slave.id)
            session_data['slave']['provider'] = actor.provider.id
        else:
            session_data['slave'] = None
        LegacySession.objects(pk=session_id).modify(
            **{'__'.join(('set', k)): v for k, v in session_data.items()},
            upsert=True)
        
    @classmethod
    def delete_session_in_v2_format(cls, sender, document, **kwargs):
        """Удаляет парную сессию в формате для api v2."""
        LegacySession.objects(pk=str(document.id)).remove()


signals.post_save.connect(Session.create_or_update_in_v2_format, sender=Session)
signals.post_delete.connect(Session.delete_session_in_v2_format, sender=Session)
