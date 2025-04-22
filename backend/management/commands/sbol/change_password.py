from mongoengine_connections import register_mongoengine_connections
from processing.soap_integration.sbol.connection import SavingsBankConnection


def main():
    register_mongoengine_connections()
    conn = SavingsBankConnection(
        'vkotolup_upg', 'cklpGH7234hc19mGOk3nfg67478GHg74bsf8',
        log_print=True
    )
    try:
        conn.fspu_connect()
        conn.change_password('cklpGH7234hc19mGOk3nfg67478GHg74bsf8')
    finally:
        conn.fspu_disconnect()

if __name__ == "__main__":
    main()

