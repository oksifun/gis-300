from mongoengine_connections import register_mongoengine_connections
from processing.soap_integration.sbol.certificate import SavingsBankCertificate
from processing.soap_integration.sbol.connection import SavingsBankConnection


def print_sber_public_key():
    register_mongoengine_connections()
    conn = SavingsBankConnection(
        'vkotolup_upg', 'gjpjIOIOhg48I38awnNd74GcEP10Yywcvjk',
        log_print=True
    )
    cert = SavingsBankCertificate(conn)
    # ВЫВЕСТИ КЛЮЧ
    key = cert.load_private_key('gost_key_temp.pem')
    pub_key = cert.get_public_key(key)
    cert.print_key_bytes(pub_key)
    h = cert.get_control_hash(pub_key)
    print(h.hex())


if __name__ == "__main__":
    print_sber_public_key()

