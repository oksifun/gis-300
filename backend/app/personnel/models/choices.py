class SystemDepartmentCode(object):
    SUPPORT = 'support'
    DIRECTION = 'direction'
    ACCOUNTING = 'accounting'
    CLERKS = 'clerks'
    STAFF = 'staff'
    FIRST_DEPARTMENT = 'first_department'
    SETTLEMENT_DEPARTMENT = 'settlement_department'


SYSTEM_DEPARTMENTS_CHOICES = (
    (SystemDepartmentCode.SUPPORT, 'Техническая поддержка'),
    (SystemDepartmentCode.DIRECTION, 'Дирекция'),
    (SystemDepartmentCode.ACCOUNTING, 'Бухгалтерия'),
    (SystemDepartmentCode.CLERKS, 'Офисные сотрудники'),
    (SystemDepartmentCode.STAFF, 'Персонал'),
    (SystemDepartmentCode.FIRST_DEPARTMENT, 'Первый отдел'),
    (SystemDepartmentCode.SETTLEMENT_DEPARTMENT, 'Расчётный отдел')
)


class SystemPositionCode(object):
    DIRECTOR = 'ch2'
    PRESIDENT = 'ch1'
    DIRECTOR_2 = 'ch3'
    ACCOUNTANT = 'acc1'


SYSTEM_POSITION_CODES_CHOICES = (
    (SystemPositionCode.PRESIDENT, 'Председатель Правления'),
    (SystemPositionCode.DIRECTOR, 'Генеральный директор'),
    (SystemPositionCode.DIRECTOR_2, 'Директор'),
    (SystemPositionCode.ACCOUNTANT, 'Главный бухгалтер'),
)
SYSTEM_POSITION_UNIQUE_CODES = (
    (
        SystemPositionCode.PRESIDENT,
        SystemPositionCode.DIRECTOR,
        SystemPositionCode.DIRECTOR_2,
    ),
    (
        SystemPositionCode.ACCOUNTANT,
    ),
)
