from rest_framework.routers import DefaultRouter

from app.tickets.api.v4.views import SupportTicketViewSet, \
    SupportTicketFilesViewSet, TicketFilesViewSet, SupportTicketCommentViewSet, \
    TenantTicketsInfoViewSet, SupportTicketConstantsViewSet

tickets_router = DefaultRouter()
tickets_router.register(
    'models/support_tickets',
    SupportTicketViewSet,
    basename='ticket'
)
tickets_router.register(
    'models/support_ticket',
    SupportTicketCommentViewSet,
    basename='ticket'
)
tickets_router.register(
    'models/support_tickets/files',
    SupportTicketFilesViewSet,
    basename='support_ticket_file'
)
tickets_router.register(
    'models/tickets/files',
    TicketFilesViewSet,
    basename='t_file'
)
tickets_router.register(
    'forms/tickets/tenant_stats',
    TenantTicketsInfoViewSet,
    basename='forms_tickets_tenant_stats'
)
tickets_router.register(
    'forms/support_tickets/constants',
    SupportTicketConstantsViewSet,
    basename='support_tickets_constants'
)
