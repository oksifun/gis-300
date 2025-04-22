from mongoengine_connections import register_mongoengine_connections
from processing.soap_integration.sbol.certificate import SavingsBankCertificate
from processing.soap_integration.sbol.connection import SavingsBankConnection


def main():
    register_mongoengine_connections()
    conn = SavingsBankConnection(
        'vkotolup_upg', 'pRm3KKa9Jenqdl46wNkr23nIfaoI3W23cIOkdwb5',
        log_print=True
    )
    cert = SavingsBankCertificate(conn)
    # СГЕНЕРИРОВАТЬ НОВЫЙ КЛЮЧ
    key = cert.generate_private_key('gost_key_temp.pem')
    cert.print_key_bytes(key)


if __name__ == "__main__":
    main()

