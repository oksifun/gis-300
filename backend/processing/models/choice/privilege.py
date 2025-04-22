
class FederalPrivilegeCode:
    DISABLED_17 = 'disabled_17'
    DISABLED_31 = 'disabled_31'
    DISABLED_KID = 'disabled_kid_federal'
    VETERAN_14 = 'veteran_14'
    VETERAN_15 = 'veteran_15'
    VETERAN_16 = 'veteran_16'
    VETERAN_17 = 'veteran_17'
    VETERAN_18 = 'veteran_18'
    VETERAN_19 = 'veteran_19'
    VETERAN_20 = 'veteran_20'
    VETERAN_21 = 'veteran_21'
    VETERAN_23 = 'veteran_23'
    CHERNOBYL_14 = 'chernobyl_14'
    ORPHAN_1 = 'orphan_1'
    ORPHAN_2 = 'orphan_2'
    REHABILITATED = 'rehabilitated'
    REHABILITATED_DEPENDENT = 'rehabilitated_dependent'
    CONCENTRATION_CAMP = 'concentration_camp'
    HERO = 'hero'
    HERO_WORKER = 'hero_worker'
    HERO_WIDOW = 'hero_widow'


class Region47PrivilegeCode:
    LARGE_FAMILY = 'large_family'
    INTELLECTUAL = 'intellectual'
    LABOUR_VETERAN = 'labour_veteran'
    SOCIAL_WORKER = 'social_worker'


class Region50PrivilegeCode:
    DISABLED_KID = 'disabled_kid'
    DISABLED_WITH_PROPERTY = 'disabled_with_property'
    EARNER_LOST = 'earner_lost'


class Region77PrivilegeCode:
    LARGE_FAMILY = 'msk_large_family'
    ALONE_80 = 'msk_alone_80'
    ALONE_70 = 'msk_alone_70'
    LABOUR_VETERAN = 'msk_labour_veteran'
    REPRESSION = 'msk_repression'
    REPRESSION_OLD = 'msk_repression_old'
    DONOR = 'msk_donor'
    ALONE_850 = 'msk_alone_850'
    HERO_850_2_1 = 'msk_hero_850_2_1'


FEDERAL_PRIVILEGE_CODES_CHOICES = (
    (
        FederalPrivilegeCode.DISABLED_17,
        'Федеральная. Закон об инвалидах. Статья 17',
    ),
    (
        FederalPrivilegeCode.DISABLED_31,
        'Федеральная. Закон об инвалидах. Статья 31',
    ),
    (
        FederalPrivilegeCode.DISABLED_KID,
        'Федеральная. Закон об инвалидах. Дети инвалиды',
    ),
    (
        FederalPrivilegeCode.VETERAN_14,
        'Федеральная. Закон о ветеранах. Статья 14',
    ),
    (
        FederalPrivilegeCode.VETERAN_15,
        'Федеральная. Закон о ветеранах. Статья 15',
    ),
    (
        FederalPrivilegeCode.VETERAN_16,
        'Федеральная. Закон о ветеранах. Статья 16',
    ),
    (
        FederalPrivilegeCode.VETERAN_17,
        'Федеральная. Закон о ветеранах. Статья 17',
    ),
    (
        FederalPrivilegeCode.VETERAN_18,
        'Федеральная. Закон о ветеранах. Статья 18',
    ),
    (
        FederalPrivilegeCode.VETERAN_19,
        'Федеральная. Закон о ветеранах. Статья 19',
    ),
    (
        FederalPrivilegeCode.VETERAN_20,
        'Федеральная. Закон о ветеранах. Статья 20',
    ),
    (
        FederalPrivilegeCode.VETERAN_21,
        'Федеральная. Закон о ветеранах. Статья 21',
    ),
    (
        FederalPrivilegeCode.VETERAN_23,
        'Федеральная. Закон о ветеранах. Статья 23',
    ),
    (
        FederalPrivilegeCode.CHERNOBYL_14,
        'Федеральная. Закон о "чернобыльцах". Статья 14',
    ),
    (
        FederalPrivilegeCode.ORPHAN_1,
        'Федеральная. Сирота',
    ),
    (
        FederalPrivilegeCode.ORPHAN_2,
        'Федеральная. Сирота (на иждивении)',
    ),
    (
        FederalPrivilegeCode.REHABILITATED,
        'Федеральная. Реабилитированные',
    ),
    (
        FederalPrivilegeCode.REHABILITATED_DEPENDENT,
        'Федеральная. Реабилитированные (иждивенец)',
    ),
    (
        FederalPrivilegeCode.CONCENTRATION_CAMP,
        'Федеральная. Узники концлагерей',
    ),
    (
        FederalPrivilegeCode.HERO,
        'Федеральная. Герои РФ, СССР',
    ),
    (
        FederalPrivilegeCode.HERO_WORKER,
        'Федеральная. Герои труда',
    ),
    (
        FederalPrivilegeCode.HERO_WIDOW,
        'Федеральная. Вдова героя',
    ),
)
REGION47_PRIVILEGE_CODES_CHOICES = (
    (
        Region47PrivilegeCode.LARGE_FAMILY,
        'Ленинградская обл. Многодетная семья',
    ),
    (
        Region47PrivilegeCode.INTELLECTUAL,
        'Ленинградская обл. Сельский интеллигент',
    ),
    (
        Region47PrivilegeCode.LABOUR_VETERAN,
        'Ленинградская обл. Ветеран труда',
    ),
    (
        Region47PrivilegeCode.SOCIAL_WORKER,
        'Ленинградская обл. Социальный работник',
    ),
)
REGION50_PRIVILEGE_CODES_CHOICES = (
    (
        Region50PrivilegeCode.DISABLED_KID,
        'Московская обл. Дети инвалиды',
    ),
    (
        Region50PrivilegeCode.DISABLED_WITH_PROPERTY,
        'Московская обл. Инвалид (есть собственность)',
    ),
    (
        Region50PrivilegeCode.EARNER_LOST,
        'Московская обл. Потеря кормильца, дети на попечении',
    ),
)
REGION77_PRIVILEGE_CODES_CHOICES = (
    (
        Region77PrivilegeCode.LARGE_FAMILY,
        'Москва. Многодетная семья',
    ),
    (
        Region77PrivilegeCode.ALONE_80,
        'Москва. Одиноко прожив.неработ.собственники, 80 лет. '
        'Статья 169 часть 2.1 ЖК РФ',
    ),
    (
        Region77PrivilegeCode.ALONE_70,
        'Москва. Одиноко прожив.неработ.собственники, 70 лет. '
        'Статья 169 часть 2.1 ЖК РФ',
    ),
    (
        Region77PrivilegeCode.LABOUR_VETERAN,
        'Москва. Ветеран труда',
    ),
    (
        Region77PrivilegeCode.REPRESSION,
        'Москва. Жертвы политических репрессий. ПП РФ №160',
    ),
    (
        Region77PrivilegeCode.REPRESSION_OLD,
        'Москва. Жертвы политических репрессий (пенсионер). ПП РФ №160',
    ),
    (
        Region77PrivilegeCode.DONOR,
        'Москва. Донор (ПП Москвы № 1282-ПП)',
    ),
    (
        Region77PrivilegeCode.ALONE_850,
        'Москва. Одиноко проживающие инвалиды/пенсионеры/семьи. '
        'ППМ от 07.12.2004 №850-ПП',
    ),
    (
        Region77PrivilegeCode.HERO_850_2_1,
        'Москва. Герои Советского Союза, Герои Российской Федерации, '
        'Полные кавалеры ордена боевой Славы. '
        'ППМ от 07.12.2004 №850-ПП (п.2.1 Порядка)',
    ),
)


class PrivilegeType:
    FEDERAL = FederalPrivilegeCode.__class__.__name__
    REGION47 = Region47PrivilegeCode.__class__.__name__
    REGION50 = Region50PrivilegeCode.__class__.__name__
    REGION77 = Region77PrivilegeCode.__class__.__name__


PRIVILEGE_TYPES_CHOICES = (
    (PrivilegeType.FEDERAL, 'Федеральные'),
    (PrivilegeType.REGION47, 'Ленинградской обл'),
    (PrivilegeType.REGION50, 'Московской обл'),
    (PrivilegeType.REGION77, 'Москвы'),
)


class PrivilegeDocumentType:
    HERO = 'hero'
    MEDAL_GLORY = 'medal_glory'
    HERO_LABOUR_USSR = 'hero_labour_ussr'
    MEDAL_LABOUR_GLORY = 'medal_labour_glory'
    HERO_LABOUR = 'hero_labour'
    GDW_DISABLED = 'gdw_disabled'
    PRIVILEGE_DISABLED = 'privilege_disabled'
    GDW_PARTICIPANT = 'gdw_participant'
    GDW_VETERAN = 'gdw_veteran'
    GDW_FREELANCER = 'gdw_freelancer'
    GDW_PARTISAN = 'gdw_partisan'
    MEDAL_LENINGRAD_DEFENCE = 'medal_leningrad_defence'
    PRIVILEGE_MOSCOW_DEFENCE = 'privilege_moscow_defence'
    MEDAL_MOSCOW_DEFENCE = 'medal_moscow_defence'
    SIGN_LENINGRAD_SIEGE = 'sign_leningrad_siege'
    PRIVILEGE_VETERAN = 'privilege_veteran'
    VETERAN_WAR = 'veteran_war'
    VETERAN_WAR_RELATIVE = 'veteran_war_relative'
    PENSION_EARNER_LOST = 'pension_earner_lost'
    CONCENTRATION_CAMP = 'concentration_camp'
    REHABILITATED = 'rehabilitated'
    REPRESSIONS1 = 'repressions1'
    REPRESSIONS2 = 'repressions2'
    CHERNOBYL_DISEASED = 'chernobyl_diseased'
    CHERNOBYL_LIQUIDATOR = 'chernobyl_liquidator'
    CHERNOBYL_VICTIM = 'chernobyl_victim'
    VETERAN_ESPECIAL_RISK = 'veteran_especial_risk'
    ESPECIAL_RISL_RELATIVE = 'especial_risk_relative'
    MAYAK_VICTIM = 'mayak_victim'
    MAYAK_LIQUIDATOR = 'mayak_liquidator'
    SEMIPALATINSK_VICTIM = 'semipalatinsk_victim'
    DONOR = 'donor'
    DONOR_MOSCOW = 'donor_moscow'
    DONOR_RUSSIAN = 'donor_russian'
    LARGE_FAMILY = 'large_family'
    MEDICAL_CERTIFICATE = 'medical_certificate'
    LABOUR_VETERAN = 'labour_veteran'
    VETERAN = 'veteran'
    PRIVILEGE_CERTIFICATE1 = 'privilege_certificate1'
    PRIVILEGE_CERTIFICATE2 = 'privilege_certificate2'
    PRIVILEGE_CERTIFICATE3 = 'privilege_certificate3'
    PENSION = 'pension'
    SCHOOL_CERTIFICATE = 'school_certificate'
    MARRIAGE = 'marriage'
    COUNCIL_DOCUMENT = 'council_document'
    PUBLIC_CARE = 'public_care'
    PENSION_INSURANCE = 'pension_insurance'


PRIVILEGE_DOCUMENT_TYPES_CHOICES = (
    (
        PrivilegeDocumentType.HERO,
        'Удостоверение Героя СССР, РФ',
    ),
    (
        PrivilegeDocumentType.MEDAL_GLORY,
        'Удостоверение к ордену Славы',
    ),
    (
        PrivilegeDocumentType.HERO_LABOUR_USSR,
        'Удостоверение Героя Соц. Труда',
    ),
    (
        PrivilegeDocumentType.MEDAL_LABOUR_GLORY,
        'Удостоверение к ордену  Трудовой Славы',
    ),
    (
        PrivilegeDocumentType.HERO_LABOUR,
        'Удостоверение Героя Труда РФ',
    ),
    (
        PrivilegeDocumentType.GDW_DISABLED,
        'Удостоверение инвалида ВОВ',
    ),
    (
        PrivilegeDocumentType.PRIVILEGE_DISABLED,
        'Удостоверение инвалида о праве на льготы (Афганистан, Чечня и т.п.)',
    ),
    (
        PrivilegeDocumentType.GDW_PARTICIPANT,
        'Удостоверение участника ВОВ',
    ),
    (
        PrivilegeDocumentType.GDW_VETERAN,
        'Удостоверение ветерана ВОВ',
    ),
    (
        PrivilegeDocumentType.GDW_FREELANCER,
        'Удостоверение вольнонаемного в период ВОВ',
    ),
    (
        PrivilegeDocumentType.GDW_PARTISAN,
        'Удостоверение партизана в период ВОВ',
    ),
    (
        PrivilegeDocumentType.MEDAL_LENINGRAD_DEFENCE,
        'Удостоверение награжденного медалью "За оборону Ленинграда"',
    ),
    (
        PrivilegeDocumentType.PRIVILEGE_MOSCOW_DEFENCE,
        'Справка о праве на льготы участника обороны Москвы',
    ),
    (
        PrivilegeDocumentType.MEDAL_MOSCOW_DEFENCE,
        'Удостоверение к медали "За оборону Москвы"',
    ),
    (
        PrivilegeDocumentType.SIGN_LENINGRAD_SIEGE,
        'Удостоверение к знаку "Жителю блокадного Ленинграда"',
    ),
    (
        PrivilegeDocumentType.PRIVILEGE_VETERAN,
        'Свидетельство о праве на льготы ветерана боевых действий',
    ),
    (
        PrivilegeDocumentType.VETERAN_WAR,
        'Удостоверение ветерана боевых действий',
    ),
    (
        PrivilegeDocumentType.VETERAN_WAR_RELATIVE,
        'Удостоверение члена семьи погибшего военнослужащего, '
        'умершего (погибшего) ИВОВ, УВОВ, ветерана боевых действий',
    ),
    (
        PrivilegeDocumentType.PENSION_EARNER_LOST,
        'Справка о пенсии по потере кормильца (ст. 21 закона РФ "О ветеранах")',
    ),
    (
        PrivilegeDocumentType.CONCENTRATION_CAMP,
        'Удостоверение несовершеннолетнего узника концлагеря ',
    ),
    (
        PrivilegeDocumentType.REHABILITATED,
        'Свидетельство  реабилитированного',
    ),
    (
        PrivilegeDocumentType.REPRESSIONS1,
        'Свидетельство пострадавшего от политических репрессий',
    ),
    (
        PrivilegeDocumentType.REPRESSIONS2,
        'Удостоверение пострадавшего от политических репрессий',
    ),
    (
        PrivilegeDocumentType.CHERNOBYL_DISEASED,
        'Удостоверение перенесшего лучевую болезнь вследствие аварии на ЧАЭС',
    ),
    (
        PrivilegeDocumentType.CHERNOBYL_LIQUIDATOR,
        'Удостоверение ликвидатора последствий аварии на ЧАЭС',
    ),
    (
        PrivilegeDocumentType.CHERNOBYL_VICTIM,
        'Удостоверение пострадавшего вследствие аварии на ЧАЭС',
    ),
    (
        PrivilegeDocumentType.VETERAN_ESPECIAL_RISK,
        'Удостоверение ветерана подразделения особого риска',
    ),
    (
        PrivilegeDocumentType.ESPECIAL_RISL_RELATIVE,
        'Справка о потере кормильца из числа лиц подразделений особого риска',
    ),
    (
        PrivilegeDocumentType.MAYAK_VICTIM,
        'Удостоверение пострадавшего вследствие аварии на ПО "МАЯК"',
    ),
    (
        PrivilegeDocumentType.MAYAK_LIQUIDATOR,
        'Удостоверение ликвидатора последствий аварии на ПО "МАЯК"',
    ),
    (
        PrivilegeDocumentType.SEMIPALATINSK_VICTIM,
        'Удостоверение пострадавшего от ядерных испытаний на '
        'Семипалатинском полигоне',
    ),
    (
        PrivilegeDocumentType.DONOR,
        'Справка о сдаче крови или плазмы',
    ),
    (
        PrivilegeDocumentType.DONOR_MOSCOW,
        'Удостоверение почетного донора Москвы',
    ),
    (
        PrivilegeDocumentType.DONOR_RUSSIAN,
        'Удостоверение почетного донора СССР, России',
    ),
    (
        PrivilegeDocumentType.LARGE_FAMILY,
        'Удостоверение многодетной семьи',
    ),
    (
        PrivilegeDocumentType.MEDICAL_CERTIFICATE,
        'Справка МСЭ (ВТЭК)',
    ),
    (
        PrivilegeDocumentType.LABOUR_VETERAN,
        'Удостоверение ветерана труда',
    ),
    (
        PrivilegeDocumentType.VETERAN,
        'Удостоверение ветерана военной службы',
    ),
    (
        PrivilegeDocumentType.PRIVILEGE_CERTIFICATE1,
        'Удостоверение о праве на льготы',
    ),
    (
        PrivilegeDocumentType.PRIVILEGE_CERTIFICATE2,
        'Свидетельство о праве на льготы',
    ),
    (
        PrivilegeDocumentType.PRIVILEGE_CERTIFICATE3,
        'Справка о праве на льготы ',
    ),
    (
        PrivilegeDocumentType.PENSION,
        'Пенсионное удостоверение',
    ),
    (
        PrivilegeDocumentType.SCHOOL_CERTIFICATE,
        'Справка из школы для детей старше 16 лет',
    ),
    (
        PrivilegeDocumentType.MARRIAGE,
        'Свидетельство о браке',
    ),
    (
        PrivilegeDocumentType.COUNCIL_DOCUMENT,
        'Распорядительный документ Главы районной Управы',
    ),
    (
        PrivilegeDocumentType.PUBLIC_CARE,
        'Справка органов опеки',
    ),
    (
        PrivilegeDocumentType.PENSION_INSURANCE,
        'Справка ПФР о назначении страховой пенсии',
    ),
)
