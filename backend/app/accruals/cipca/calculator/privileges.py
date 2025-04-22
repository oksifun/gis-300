import copy
from decimal import Decimal


class PrivilegesCalculator:

    def __init__(self, parent_calculator, max_value_service_isolated=True):
        self._parent = parent_calculator
        self.max_value_service_isolated = max_value_service_isolated

    def calculate_debt(self, debt, allow_rob=True):
        # сгруппируем жителей
        tenants = {}
        for privilege in debt.account_data['default']['privileges']:
            if privilege['is_individual']:
                t = tenants.setdefault(str(privilege['tenant']), [])
                t.append(privilege)
        # посчитаем каждого жителя
        results = self.get_all_privileges_results(debt, tenants)
        if allow_rob and len(tenants) > 1:
            # попробуем поотнимать льготы у кого-нибудь
            original_privileges = copy.deepcopy(
                debt.account_data['default']['privileges'])

            def merge_results(r_in, r_out):
                ss_in = {}
                for r in r_in:
                    for s, d in r['services'].items():
                        ss_in.setdefault(s, 0)
                        ss_in[s] += d['value']
                ss_out = {}
                for r in r_out:
                    for s, d in r['services'].items():
                        ss_out.setdefault(s, 0)
                        ss_out[s] += d['value']
                to_replace = []
                for s, v in ss_in.items():
                    if v < ss_out.get(s, 0):
                        to_replace.append(s)
                for s in ss_out:
                    if s not in ss_in:
                        to_replace.append(s)
                for s in to_replace:
                    for r in r_in:
                        if s in r['services']:
                            r['services'].pop(s)
                    for r in r_out:
                        if s not in r['services']:
                            continue
                        r_t = None
                        for r_i in r_in:
                            if r_i['tenant'] == r['tenant']:
                                r_t = r_i
                                break
                        if not r_t:
                            r_t = {
                                'tenant': r['tenant'],
                                'total': 0,
                                'services': {},
                                'privilege': r['privilege']
                            }
                            r_in.append(r_t)
                        r_t['services'][s] = r['services'][s]

            def fun(tenants_r, privilegers):
                o_p = copy.deepcopy(
                    debt.account_data['default']['privileges'],
                )
                tt_remain = {t: tenants_r[t] for t in privilegers}
                for p in debt.account_data['default']['privileges']:
                    p['family'] = None
                    if str(p['tenant']) not in privilegers:
                        p['is_individual'] = False
                for t, data in tenants_r.items():
                    for d in data:
                        d['family'] = None
                    if t not in privilegers:
                        for d in data:
                            d['is_individual'] = False
                r_r = self.get_all_privileges_results(debt, tt_remain)
                merge_results(results, r_r)
                debt.account_data['default']['privileges'] = o_p

            def get_combinations(tenants_r):
                result = []
                b = '1'
                for i in range(2 ** len(tenants_r)):
                    r = set()
                    for ix, c in enumerate(bin(i)[2:].zfill(len(tenants_r))):
                        if c == b:
                            r.add(tenants_r[ix])
                    result.append(r)
                return result

            for ix, tenants_comb in enumerate(get_combinations(list(tenants))):
                fun(tenants, tenants_comb)
            debt.account_data['default']['privileges'] = original_privileges

        return results

    def get_all_privileges_results(self, debt, tenants):
        used_area = {}
        used_norma = {}
        results = []
        ix = 0
        for tenant, privileges in tenants.items():
            ix += 1
            self._parent.add_value_to_buffer(debt, 'текущий_льготник', None, ix)
            result = self.get_tenant_privileges_result(
                debt,
                privileges,
                self._parent.regional_settings,
                used_area,
                used_norma,
            )
            for s, r in result['services'].items():
                used_area.setdefault(s, 0)
                used_area[s] += Decimal(r['area'])
                used_norma.setdefault(s, 0)
                used_norma[s] += r['consumption']
            result['tenant'] = tenant
            results.append(result)
        return results

    def get_tenant_privileges_result(self, debt, privileges, regional_settings,
                                     used_area, used_norma):
        """
        Считает каждую категорию полностью по всем статьям, выбирает лучший
        результат и возвращает. Результатом будет для каждой статьи сумма, а
        также расход и площадь, которые были отданы на расчёт этому льготнику
        """
        # считаем каждую категорию
        results = {}
        for privilege in privileges:
            # найдём настройки расчёта
            rules = self._get_regional_privilege_settings(
                privilege['privilege'],
                debt.account_data['main']['tenant']['property_type'],
                regional_settings,
                [s['service_type'] for s in debt.doc_m['services']]
            )
            # посчитаем льготу
            results[privilege['privilege']] = self._get_privilege_result(
                debt, privilege, rules, used_area, used_norma
            )
            results[privilege['privilege']]['privilege'] = privilege

        # ВЫБИРАЕМ МАКСИМАЛЬНУЮ ЛЬГОТУ

        result = {'total': 0, 'services': {}}
        if self.max_value_service_isolated:
            # 1 вариант - постатейно
            for r in results.values():
                for s, data in r['services'].items():
                    data['privilege'] = r['privilege']
                    if s in result['services']:
                        if data['value'] > result['services'][s]['value']:
                            result['services'][s] = data
                    else:
                        result['services'][s] = data
        else:
            # 2 вариант - выбор одной категории
            for r in results.values():
                for data in r['services'].values():
                    data['privilege'] = r['privilege']
                if r['total'] > result['total']:
                    result = r
        return result

    def _get_regional_privilege_settings(self, category, property_type,
                                         regional_settings, service_types):
        """
        Для каждой статьи выбирает настройки расчёта и привязку льготы
        """
        result = {}
        privilege_code = regional_settings['privilege_codes'].get(category)
        if not privilege_code:
            return result
        # ищем в системном тарифном плане расчёт по тарифам
        if regional_settings['tariff_plans']:
            tp = regional_settings['tariff_plans'][0]
            for tariff in tp['tariffs']:
                if tariff['service_type'] in service_types:
                    result[tariff['service_type']] = {
                        'rule': tariff,
                        'p_bind': None
                    }
        # ищем привязки
        for s_type, r in result.items():
            for p_template in regional_settings['privileges']:
                if (
                    len(p_template['property_types']) > 0 and
                    property_type not in p_template['property_types']
                ):
                    continue
                if s_type not in p_template['service_types']:
                    continue
                for p_bind in p_template['privileges_binds']:
                    if p_bind['privilege'] == privilege_code:
                        r['p_bind'] = p_bind
                        break
        return {k: v for k, v in result.items() if v['p_bind'] and v['rule']}

    def _get_privilege_result(self, debt, tenant_privilege, calculate_rules,
                              used_area, used_norma):
        result = {'total': 0, 'services': {}}
        # формируем очередь услуг для расчёта
        sys_queue = self._parent.get_calculate_queue()
        ready_services = []
        queue = []
        for q in sys_queue:
            q_ids = [s['_id'] for s in q if s['_id'] in calculate_rules]
            if q_ids:
                ready_services.extend(q_ids)
                queue.append(q_ids)
        left_services = set(calculate_rules.keys()) - set(ready_services)
        if left_services:
            queue.append(list(left_services))
        # считаем
        for s_types in queue:
            services = self._prepare_services_list(
                s_types,
                debt,
                tenant_privilege,
                calculate_rules,
            )
            for service in services:
                s_type = service['service_type']
                # if str(s_type) in ('526234c0e0e34c4743822326',  # отопление МОП
                #                    '526234c0e0e34c4743822338'):  # отопление
                # if str(s_type) == '56fa5c01401aac2a8a522e95':  # ээ пик
                # if str(s_type) == '56fa5c0c401aac2a8a522e96':  # ээ полупик
                # if str(s_type) == '526234c0e0e34c4743822341':  # ХВ
                # if str(s_type) == '526234c0e0e34c474382232f':  # ГВ
                # if str(s_type) == '526234c0e0e34c4743822329':  # ГВ на ОДН
                # if str(s_type) == '526234c0e0e34c4743822327':  # ХВ на ОДН
                # if str(s_type) == '526234c0e0e34c474382233d':  # сои
                #     rule = debt.get_service_rule(s_type)
                rule = debt.get_service_rule(s_type)
                if rule['settings']['calc_type'] != 'own':
                    rule = calculate_rules[s_type]['rule']
                result['services'][s_type] = self._get_privilege_service_result(
                    debt,
                    service,
                    rule,
                    calculate_rules[s_type]['rule'],
                    tenant_privilege,
                    calculate_rules[s_type]['p_bind'],
                    used_area.get(s_type, 0),
                    used_norma.get(s_type, 0)
                )
        result['total'] = sum(s['value'] for s in result['services'].values())
        return result

    def _prepare_services_list(self, services_ids, debt, tenant_privilege,
                               calculate_rules):
        services = []
        for s_type in services_ids:
            rule = debt.get_service_rule(s_type)
            if not rule['settings']['use_privileges']:
                continue
            urban_rule = calculate_rules[s_type]['rule']
            # подготовим расчёт
            temp_service = copy.deepcopy(debt.services_dict[s_type])
            temp_service.setdefault('temp', {})
            temp_service['temp']['sys_social_area_settings'] = \
                self.extract_system_social_area_settings(urban_rule)
            services.append(temp_service)
        return sorted(
            services,
            key=lambda i: -i['tariff'],
        )

    def extract_system_social_area_settings(self, rule):
        social_normas = {}
        for a_value in rule['add_values']:
            if 'SN' in a_value['title']:
                social_normas[a_value['title']] = {
                    'value': a_value['value'],
                    'formula': 'Т[value={}]*КЧЛГ'.format(
                        a_value['title'],
                    ),
                }
        for a_fml in rule['formulas']['additional']:
            if 'SN' in a_fml['title']:
                sn = social_normas.setdefault(
                    a_fml['title'],
                    {'value': 0},
                )
                sn['formula'] = a_fml['value']
        return social_normas

    def _get_privilege_service_result(self, debt, service, rule, urban_rule,
                                      tenant_privilege, p_bind, used_area,
                                      used_norma):
        # подготовим расчёт
        self._parent.pre_calculate_debt(
            debt,
            service,
            rule,
            privilege_data={
                'privilege': tenant_privilege,
                'sys_social_area_settings':
                    service['temp']['sys_social_area_settings'],
                'bind': p_bind,
            },
        )
        # посчитаем площадь
        area = self._calculate_privilege_area(
            debt,
            service,
            rule,
            tenant_privilege,
            p_bind,
            used_area,
        )
        # посчитаем норматив
        norma, area_in_consumption = self._calculate_privilege_norma(
            debt,
            service,
            rule,
            urban_rule,
            tenant_privilege,
            p_bind,
            used_norma,
            area,
        )
        # посчитаем сумму
        result = self._calculate_privilege_value(
            debt,
            service,
            rule,
            tenant_privilege,
            p_bind,
            norma,
            area,
        )
        result['consumption'] = norma
        result['area'] = area
        result['area_used'] = result['area_used'] or area_in_consumption
        return result

    def _calculate_privilege_norma(self, debt, service, rule, urban_rule,
                                   tenant_privilege, p_bind, used_norma, area):
        """
        Считает льготный объём коммунальной услуги. Дополнительно проверяет,
        используется ли площадь в расчёте объёма. Таким образом, возвращает
        полученный объём и флаг использования площади
        """
        area_in_consumption = 'ПЛОЩАДЬ' in service['temp']['formula_consumption']
        if p_bind['calc_option'] not in ('consumption_norma',
                                         'consumption_norma_manual',
                                         'social_consumption_norma',
                                         'social_consumption_norma_manual'):
            origin_area = service['temp']['square']
            if p_bind['calc_option'] == 'social_norma' and area_in_consumption:
                service['temp']['square'] = area
                fml = service['temp']['formula_consumption']
            else:
                fml = '{}/КЧПР'.format(service['consumption'])
                if p_bind['scope'] == 'family':
                    fml = '{}*КЧЛГ'.format(fml)
            norma = self._parent.calculate_privilege_formula(
                fml,
                debt,
                service,
                rule,
                privilege=tenant_privilege,
                custom_normas={},
                privilege_bind=p_bind,
            )
            norma = min(norma, service['consumption'] - used_norma)
            service['temp']['square'] = origin_area
            return norma, area_in_consumption
        if used_norma >= service['consumption']:
            return 0, area_in_consumption
        origin_area = service['temp']['square']
        formula_coef = ''
        if p_bind['calc_option'] in ('social_consumption_norma',
                                     'social_consumption_norma_manual'):
            service['temp']['square'] = area
            if area != origin_area:
                formula_coef = f'ПЛОЩАДЬ/{origin_area}'
        norma_formula = self._parent.get_norma_formula(
            debt,
            service,
            rule,
            privilege_data={
                'privilege': tenant_privilege,
                'sys_social_area_settings':
                    service['temp']['sys_social_area_settings'],
                'bind': p_bind,
            },
        )
        if norma_formula:
            if formula_coef and 'ПЛОЩАДЬ' not in norma_formula:
                norma_formula = f'{norma_formula}*{formula_coef}'
            norma = self._parent.calculate_privilege_formula(
                norma_formula,
                debt,
                service,
                rule,
                privilege=tenant_privilege,
                custom_normas={},
                privilege_bind=p_bind,
            )
        else:
            norma_formula = self._parent.get_norma_formula(
                debt,
                service,
                urban_rule,
                privilege_data={
                    'privilege': tenant_privilege,
                    'sys_social_area_settings':
                        service['temp']['sys_social_area_settings'],
                    'bind': p_bind,
                },
            )
            if formula_coef and 'ПЛОЩАДЬ' not in norma_formula:
                norma_formula = f'{norma_formula}*{formula_coef}'
            norma = self._parent.calculate_privilege_formula(
                norma_formula,
                debt,
                service,
                urban_rule,
                privilege=tenant_privilege,
                custom_normas={},
                privilege_bind=p_bind,
            )
        if p_bind['calc_option'] == 'consumption_norma':
            fml = '{}/КЧПР'.format(norma)
            if p_bind['scope'] == 'family':
                fml = '{}*КЧЛГ'.format(fml)
            norma = self._parent.calculate_privilege_formula(
                fml,
                debt,
                service,
                rule,
                privilege=tenant_privilege,
                custom_normas={},
                privilege_bind=p_bind,
            )
        service['temp']['square'] = origin_area
        norma = min(norma, service['consumption'] - used_norma)
        if p_bind['isolated']:
            fml = '{}/КЧПР'.format(service['consumption'])
            if p_bind['scope'] == 'family':
                fml = '{}*КЧЛГ'.format(fml)
            share = self._parent.calculate_privilege_formula(
                fml,
                debt,
                service,
                rule,
                privilege=tenant_privilege,
                custom_normas={},
                privilege_bind=p_bind,
            )
            norma = min(norma, share)
        if p_bind.get('buffer_name'):
            self._parent.add_value_to_buffer(
                debt,
                p_bind['buffer_name'],
                service['service_type'],
                norma,
                inc=True,
            )
        return norma, area_in_consumption

    def _calculate_privilege_area(self, debt, service, rule,
                                  tenant_privilege, p_bind, used_area):
        if used_area >= service['temp']['square']:
            return 0
        # сформируем формулу
        if p_bind['calc_option'] in ('social_norma',
                                     'social_consumption_norma',
                                     'social_consumption_norma_manual'):
            if service['temp']['sys_social_area_settings']:
                fml = 'ВНУТРНОРМА'
            else:
                fml = '{}/КЧПР'.format(str(service['temp']['area_social']))
        else:
            fml = 'ПЛОЩАДЬ/КЧПР'
        if p_bind['scope'] == 'family':
            fml = '{}*КЧЛГ'.format(fml)
        # посчитаем площадь
        area = Decimal(self._parent.calculate_privilege_formula(
            fml,
            debt,
            service,
            rule,
            privilege=tenant_privilege,
            custom_normas=service['temp']['sys_social_area_settings'],
            privilege_bind=p_bind,
        ))
        area = min(
            area,
            Decimal(service['temp']['square']) - Decimal(used_area),
        )
        if p_bind['isolated']:
            criteria = service['temp'].get('social_norma_criteria', 'КЧПР')
            fml = '{}/{}'.format(service['temp']['square'], criteria)
            if p_bind['scope'] == 'family':
                fml = '{}*КЧЛГ'.format(fml)
            share = self._parent.calculate_privilege_formula(
                fml,
                debt,
                service,
                rule,
                privilege=tenant_privilege,
                custom_normas={},
                privilege_bind=p_bind,
            )
            area = min(area, share)
        return area

    def _calculate_privilege_value(self, debt, service, rule,
                                   tenant_privilege, p_bind, norma, area):
        consumption_used = False
        area_used = False
        # if p_bind['calc_option'] == 'social_norma':
        #     fml = 'ТАРИФ*{}'.format(area)
        #     area_used = True
        if p_bind['calc_option'] in ('consumption_norma',
                                       'consumption_norma_manual',
                                       'social_consumption_norma'):
            fml = 'ТАРИФ*{}'.format(norma)
            consumption_used = True
            if p_bind['calc_option'] == 'social_consumption_norma':
                area_used = True
        else:
            if (
                    (service['consumption'] or not service['value'])
                    and service['consumption'] != service['temp']['square']
            ):
                fml = 'ТАРИФ*{}'.format(norma)
                consumption_used = True
            else:
                fml = 'ТАРИФ*{}'.format(area)
                area_used = True
            if p_bind['calc_option'] == 'property_share':
                fml = '{}*ДОЛЯСОБЛГ'.format(fml)

        fml = '{}/100*{}'.format(str(p_bind['rate']), fml)
        value = self._parent.calculate_privilege_formula(
            fml,
            debt,
            service,
            rule,
            privilege=tenant_privilege,
            custom_normas={},
            privilege_bind=p_bind,
        )
        count = 1 if p_bind['scope'] == 'person' else 'family'
        return {
            'value': value,
            'count': count,
            'consumption_used': consumption_used,
            'area_used': area_used,
        }
