from app.permissions.workers.config import joker_app
from mongoengine_connections import register_mongoengine_connections


@joker_app.on_after_configure.connect
def register_mongo_connections(sender, **kwargs):
    register_mongoengine_connections()


if __name__ == '__main__':
    joker_app.start()
