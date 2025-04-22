from app.personnel.models.department import Department


def get_provider_ticket_departments(provider_id):
    query = {
        'settings__tenant_tickets': True,
        'provider': provider_id,
    }
    return list(Department.objects(**query))
