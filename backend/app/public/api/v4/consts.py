# последние 4 цифры телефонов с которых осуществляется дозвон
# здесь пока один номер, но может быть и больше
import settings

TELEPHONE_CODES = (
    '6744',
    '1076',
)
# POSSIBLE_TELEPHONE_CODES = (
#     '2778',
#     '3780',
#     '1076',
#     '4113',
#     '5374',
#     '1843',
#     '2610',
# )

SOURCE_SIM = 'sim=2'
HOST = 'https://lk.eis24.me'
if settings.DEVELOPMENT:
    HOST = 'https://stage.eis24.me'

TASK_RUNNER_URL = '{}/api/v4/public_qr/dialing/'.format(HOST)
