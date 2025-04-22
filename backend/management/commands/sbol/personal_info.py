from mongoengine_connections import register_mongoengine_connections
from processing.soap_integration.sbol.certificate import SavingsBankCertificate
from processing.soap_integration.sbol.connection import SavingsBankConnection
from processing.soap_integration.sbol.message import SavingsBankMessage


def main():
    register_mongoengine_connections()
    conn = SavingsBankConnection(
        'vkotolup_upg', 'gjpjIOIOhg48I38awnNd74GcEP10Yywcvjk',
        log_print=True
    )
    try:
        conn.fspu_connect()
        conn.login()
        cert = SavingsBankCertificate(conn)
        # ИНФОРМАЦИЯ О СЕБЕ
        r = SavingsBankMessage(conn, cert)
        r.get_personal_info()
        # cert.activate_certificate(
        #     issuer='CN=УЦ ПАО Сбербанк',
        #     serial_number='787DA31B4FEA82712D60'
        # )
    finally:
        conn.fspu_disconnect()


if __name__ == "__main__":
    main()

