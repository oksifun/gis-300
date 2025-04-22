from mongoengine_connections import register_mongoengine_connections
from processing.soap_integration.sbol.certificate import SavingsBankCertificate
from processing.soap_integration.sbol.connection import SavingsBankConnection


def send_certificate_request_to_sber():
    register_mongoengine_connections()
    conn = SavingsBankConnection(
        'vkotolup_upg', 'gjpjIOIOhg48I38awnNd74GcEP10Yywcvjk',
        log_print=True
    )
    try:
        # conn.fspu_connect()
        # conn.login()
        cert = SavingsBankCertificate(conn)
        # СОЗДАТЬ СЕРТИФИКАТ
        key = cert.load_private_key('gost_key_temp.pem')
        cert.get_new_certificate(key)
    finally:
        conn.fspu_disconnect()


if __name__ == "__main__":
    send_certificate_request_to_sber()

