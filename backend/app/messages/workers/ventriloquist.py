from app.messages.workers.config import ventriloquist
from mongoengine_connections import register_mongoengine_connections


@ventriloquist.on_after_configure.connect
def register_mongo_connections(sender, **kwargs):
    register_mongoengine_connections(secondary_prefered=True)


if __name__ == '__main__':
    ventriloquist.start()
