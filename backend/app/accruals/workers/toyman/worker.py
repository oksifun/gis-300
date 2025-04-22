from app.celery_admin.workers.config import celery_app
from mongoengine_connections import register_mongoengine_connections


@celery_app.on_after_configure.connect
def register_mongo_connections(sender, **kwargs):
    register_mongoengine_connections(secondary_prefered=True)


if __name__ == '__main__':
    celery_app.start()
