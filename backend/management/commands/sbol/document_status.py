from mongoengine_connections import register_mongoengine_connections
from processing.soap_integration.sbol.certificate import SavingsBankCertificate
from processing.soap_integration.sbol.connection import SavingsBankConnection
from processing.soap_integration.sbol.message import SavingsBankMessage


def main():
    register_mongoengine_connections()
    conn = SavingsBankConnection(
        'vkotolup_upg', 'U4Lmq7Rbjq4[uxXp8v3a5k9wh@vuqMd52F',
        log_print=True
    )
    try:
        conn.fspu_connect()
        conn.login()
        cert = SavingsBankCertificate(conn)
        # ПОЛУЧИТЬ СТАТУС ДОКУМЕНТА
        r = SavingsBankMessage(conn, cert)
        r.get_doc_status('65a2f8a8-c552-4ee5-b56a-06af2b192ac3')
        r.get_doc_status('a0746f70-3491-48bc-9f99-803910df2ac2')
    finally:
        conn.fspu_disconnect()


if __name__ == "__main__":
    main()

