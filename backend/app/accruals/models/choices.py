class CountType:
    FULL = 'full'
    REVERSE = 'reverse'


COUNT_TYPE_CHOICES = (
    # Печатать ли квитанции жителям
    (CountType.FULL, 'Общее количество'),
    (CountType.REVERSE, 'Количество по наличию'),
)
