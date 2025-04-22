

class RoomType(object):
    LIVING = 'living'
    KITCHEN = 'kitchen'
    CORRIDOR = 'corridor'
    WC = 'wc'


ROOM_TYPE_CHOICES = (
    (RoomType.LIVING, 'жилая комната'),
    (RoomType.KITCHEN, 'кухня'),
    (RoomType.CORRIDOR, 'коридор'),
    (RoomType.WC, 'санузел'),
)


class RoomPlan(object):
    BEHIND_WALK_THROUGH = 'behind_walk_through'
    BEHIND_WALK_THROUGH_LOGGIA = 'behind_walk_through_loggia'
    ISOLATED = 'isolated'
    ISOLATED_LOGGIA = 'isolated_loggia'
    WALK_THROUGH = 'walk_through'
    WALK_THROUGH_LOGGIA = 'walk_through_loggia'
    ADJOINED = 'adjoined'


ROOM_PLAN_CHOICES = (
    (RoomPlan.BEHIND_WALK_THROUGH, 'Запроходная'),
    (RoomPlan.BEHIND_WALK_THROUGH_LOGGIA, 'Запроходная/лоджия'),
    (RoomPlan.ISOLATED, 'Изолированная'),
    (RoomPlan.ISOLATED_LOGGIA, 'Изолированная/лоджия'),
    (RoomPlan.WALK_THROUGH, 'Проходная'),
    (RoomPlan.WALK_THROUGH_LOGGIA, 'Проходная/лоджия'),
    (RoomPlan.ADJOINED, 'Смежная'),
)


class RoomForm(object):
    SQUARE = 'square'
    RECTANGULAR = 'rectangular'
    WRONG = 'wrong'


ROOM_FORM_CHOICES = (
    (RoomForm.SQUARE, 'Квадратная'),
    (RoomForm.RECTANGULAR, 'Прямоугольная'),
    (RoomForm.WRONG, 'Неправильная'),
)


class RoomEntry(object):
    FROM_ROOM = 'from_room'
    FROM_CORRIDOR = 'from_corridor'


ROOM_ENTRY_CHOICES = (
    (RoomEntry.FROM_ROOM, 'из комнаты'),
    (RoomEntry.FROM_CORRIDOR, 'из коридора'),
)


class RoomBalcony(object):
    HAS = 'has'
    HAS_NOT = 'hasnt'


ROOM_BALCONY_CHOICES = (
    (RoomBalcony.HAS, 'есть'),
    (RoomBalcony.HAS_NOT, 'нет'),
)


class RoomFloor(object):
    PARQUET = 'parquet'
    LAMINATE = 'laminate'
    LINOLEUM = 'linoleum'
    BOARDWALK = 'Boardwalk'
    GRANITE = 'granite'


ROOM_FLOOR_CHOICES = (
    (RoomFloor.PARQUET, 'паркет'),
    (RoomFloor.LAMINATE, 'ламинат'),
    (RoomFloor.LINOLEUM, 'линолеум'),
    (RoomFloor.BOARDWALK, 'дощатый'),
    (RoomFloor.GRANITE, 'керамогранит'),
)


class RoomRepair(object):
    HAS = 'has'
    HAS_NOT = 'hasnt'


ROOM_REPAIR_CHOICES = (
    (RoomRepair.HAS, 'есть'),
    (RoomRepair.HAS_NOT, 'нет'),
)


class RoomEngineeringStatus(object):
    GOOD = 'good'
    SATISFACT = 'satisfact'
    BAD = 'bad'
    EMERGENCY = 'emergency'


ROOM_ENGINEERING_STATUS_CHOICES = (
    (RoomEngineeringStatus.GOOD, 'хорошее'),
    (RoomEngineeringStatus.SATISFACT, 'удовлетворительное'),
    (RoomEngineeringStatus.BAD, 'плохое'),
    (RoomEngineeringStatus.EMERGENCY, 'аварийное'),
)


class KitchenLocation(object):
    SEPARATE = 'separate'
    DINING = 'dining'


KITCHEN_LOCATION_CHOICES = (
    (KitchenLocation.SEPARATE, 'в отд.помещении'),
    (KitchenLocation.DINING, 'кухня-столовая'),
)


class KitchenLighting(object):
    LIGHT = 'light'
    DARK = 'dark'


KITCHEN_LIGHTING_CHOICES = (
    (KitchenLighting.LIGHT, 'светлая'),
    (KitchenLighting.DARK, 'темная'),
)


class WCType(object):
    SEPARATE = 'separate'
    COMBINED = 'combined'


WC_TYPE_CHOICES = (
    (WCType.SEPARATE, 'раздельный'),
    (WCType.COMBINED, 'совмещенный'),
)


class RoomDefects(RoomRepair):
    pass


ROOM_DEFECTS_CHOICES = (
    (RoomDefects.HAS, 'есть'),
    (RoomDefects.HAS_NOT, 'нет'),
)
