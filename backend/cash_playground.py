from aiohttp import web

from processing.online_cash_imitator.server import app


def start_app(argv):
    return app


if __name__ == '__main__':
    web.run_app(app, host='localhost', port=8087)
