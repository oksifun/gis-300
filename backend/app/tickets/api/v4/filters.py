from mongoengine import Q
from rest_framework.filters import BaseFilterBackend

from api.v4.base_crud_filters import ParamsFilter
from processing.models.billing.provider.main import Provider
from app.personnel.models.personnel import Worker


class CustomParamsFilter(ParamsFilter):
    EXCLUDE_FIELDS = [
        'theme',
        'author_name',
        'worker_type',
        'tick_mobile',
        'tick_tenant',
        'created_by___type',
        'redmine',
        'manager',
        'position',
        'department',
    ]


class CustomFilter(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        if view.action != 'list':
            return queryset
        rqp = request.query_params
        if rqp:
            query_filter = Q()
            if rqp.get('status'):
                query_filter &= Q(status=rqp.get('status'))
                print(query_filter)
            if rqp.get('author_name'):
                query_filter &= Q(initial__str_name__icontains=rqp.get('author_name'))
                # authors = SupportTicket.objects(query_filter).only('initial.author')
                # print([author.id for author in authors])
                # workers = Worker.objects(str_name__icontains=rqp.get('author_name')).only('id')
                # print(len(workers), workers)
            if rqp.get('tick_tenant') == 'true':
                query_filter &= Q(__raw__={'created_by._type': 'Tenant'})
            if rqp.get('tick_mobile') == 'true':
                query_filter &= Q(__raw__={'metadata.type': 'mobile'})
            if rqp.get('tags'):
                query_filter &= Q(tags__in=rqp.getlist('tags'))
            if rqp.get('redmine') == 'false':
                query_filter &= Q(__raw__={'redmine': {'$exists': True}})
                # query_filter &= Q(__raw__={'redmine.is_completed': True})
                # query_filter &= Q(__raw__={'redmine.is_completed': False})
            elif rqp.get('redmine') == 'true':
                # print(rqp.get('redmine.is_completed'))
                query_filter &= Q(__raw__={'redmine': {'$exists': False}})
            if rqp.get('manager'):
                query = dict(managers=rqp.get('manager'))
                providers = [p['id'] for p in Provider.objects(**query).only('id')]
                # query_filter &= Q(created_by__department__provider__in=providers)
                query_filter &= (Q(__raw__={'created_by.department.provider': {'$in': providers}}))
                return queryset.filter(query_filter)
            workers = []
            # if rqp.get('worker'):
            #     workers = Worker.objects(_id=rqp.get('worker')).only('id')
            if rqp.get('position'):
                workers = Worker.objects(position__id=rqp.get('position')).only('id')
            elif rqp.get('department'):
                workers = Worker.objects(department__id=rqp.get('department')).only('id')
            workers_ids = [w['id'] for w in workers]
            # ts = SupportTicket.objects(Q(spectators__Account__allow__in=workers_ids))
            print(workers_ids)
            # workers_ids = [ObjectId("526236dce0e34c4743827329")]
            # ts = SupportTicket.objects(__raw__={'spectators.Department.allow': {'$in': workers_ids}})
            # print('ts', ts)
            if workers_ids:
                if rqp.get('worker_type') == 'spectators':
                    # query_filter &= (Q(__raw__={'spectators.Department.allow': {'$in': workers_ids}}))
                    query_filter &= (
                            Q(spectators__Account__allow__in=workers_ids) |
                            Q(spectators__Position__allow__in=workers_ids) |
                            Q(spectators__Department__allow__in=workers_ids)
                    )
                else:
                    query_filter &= Q(executor__id__in=workers_ids)
            # print(query_filter)
            queryset = queryset.filter(query_filter)
        return queryset