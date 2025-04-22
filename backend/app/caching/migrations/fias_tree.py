from app.auth.models.actors import Actor, RoboActor
from app.caching.models.fias_tree import AccountFiasTree


def copy_fias_tree_from_worker_to_actor(worker_id):
    actor = Actor.objects(
        owner__id=worker_id,
    ).only(
        'id',
    ).as_pymongo().first()
    if not actor:
        return
    tree = AccountFiasTree.objects(
        account=worker_id,
    ).as_pymongo().first()
    if not tree:
        return
    _copy_fias_tree(tree, actor['_id'])


def copy_fias_tree_from_provider_to_actor(provider_id):
    actor = RoboActor.get_default_robot(provider_id)
    if not actor:
        return
    tree = AccountFiasTree.get_provider_tree_queryset(
        provider_id=provider_id,
    ).as_pymongo().first()
    if not tree:
        return
    _copy_fias_tree(tree, actor['_id'])


def _copy_fias_tree(tree, actor_id):
    tree.pop('_id', None)
    tree['account'] = actor_id
    AccountFiasTree.objects(
        account=actor_id,
    ).upsert_one(
        __raw__={
            '$set': tree,
        },
    )
