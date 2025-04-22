from processing.models.billing.regional_settings import RegionalSettings


def get_system_tariffs_tree(region_code):
    r_settings = RegionalSettings.objects.as_pymongo().get(
        region_code=region_code)
    return r_settings['tariff_plans']


def get_privileges_settings_list(region_code):
    r_settings = RegionalSettings.objects.as_pymongo().get(
        region_code=region_code)
    return r_settings['_id'], r_settings['privilege_plans']

