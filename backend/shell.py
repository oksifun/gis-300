import pymongo
import bson
import readline
import sys
import traceback
import re
import argparse
import pprint
from tornado import gen
from tornado.stack_context import StackContext
from tornado.ioloop import IOLoop
from tornado_legacy.core.model import Model
from tornado_legacy.core.model.actor import ACTOR_UNRESTRICTED
from tornado_legacy.core.requestlocals import RequestLocals
from tornado_legacy.core.util import is_future, utcnow
from codeop import CommandCompiler
import settings
from tornado_legacy.models.businesstype import BusinessType
from tornado_legacy.models.tab import Tab


class InteractiveInterpreter:
    def __init__(self, locals=None):
        if locals is None:
            locals = {'__name__': '__console__', '__doc__': None}

        self.locals = locals
        self.locals['gen'] = gen
        self.compile = CommandCompiler()
        self.locals['_'] = None
        self.locals['pp'] = pprint.pprint
        self.locals['pymongo'] = pymongo
        self.locals['MongoClient'] = pymongo.MongoClient
        self.locals['ObjectId'] = bson.ObjectId
        self.locals['utcnow'] = utcnow

        for model_name, model in Model.MODELS_BY_NAME.items():
            self.locals[model_name] = model

    def runsource(self, source, filename='<input>', symbol='single'):
        code = self.compile(source, filename, symbol)

        if code is None:
            return True

        exec(code, self.locals)
        return False

    def showsyntaxerror(self, filename=None):
        type, value, tb = sys.exc_info()
        sys.last_type = type
        sys.last_value = value
        sys.last_traceback = tb

        if filename and type is SyntaxError:
            try:
                msg, (dummy_filename, lineno, offset, line) = value.args
            except ValueError:
                pass
            else:
                value = SyntaxError(msg, (filename, lineno, offset, line))
                sys.last_value = value

        if sys.excepthook is sys.__excepthook__:
            lines = traceback.format_exception_only(type, value)
            self.write(''.join(lines))
        else:
            sys.excepthook(type, value, tb)

    def showtraceback(self):
        sys.last_type, sys.last_value, last_tb = ei = sys.exc_info()
        sys.last_traceback = last_tb

        try:
            lines = []

            for value, tb in traceback._iter_chain(*ei[1:]):
                if isinstance(value, str):
                    lines.append(value)
                    lines.append('\n')
                    continue

                if tb:
                    tblist = traceback.extract_tb(tb)
                    if tb is last_tb:
                        del tblist[:1]
                    tblines = traceback.format_list(tblist)
                    if tblines:
                        lines.append('Traceback (most recent call last):\n')
                        lines.extend(tblines)

                lines.extend(
                    traceback.format_exception_only(
                        type(value),
                        value,
                    ),
                )
        finally:
            tblist = last_tb = ei = None
        if sys.excepthook is sys.__excepthook__:
            self.write(''.join(lines))
        else:
            sys.excepthook(type, value, last_tb)

    def write(self, data):
        sys.stderr.write(data)


class InteractiveConsole(InteractiveInterpreter):
    def __init__(self, locals=None, filename='<console>'):
        InteractiveInterpreter.__init__(self, locals)
        self.filename = filename
        self.resetbuffer()

    def resetbuffer(self):
        self.buffer = []

    def interact(self, banner=None):
        try:
            sys.ps1
        except AttributeError:
            sys.ps1 = '> '
        try:
            sys.ps2
        except AttributeError:
            sys.ps2 = '> '
        cprt = \
            'Type "help", "copyright", "credits" or "license" ' \
            'for more information.'

        if banner:
            self.write('%s\n' % str(banner))

        more = 0

        while 1:
            try:
                if more:
                    prompt = sys.ps2
                else:
                    prompt = sys.ps1
                try:
                    line = self.raw_input(prompt)
                except EOFError:
                    self.write('\n')
                    break
                else:
                    try:
                        more = self.push(line)
                    except Exception as e:
                        traceback.print_exc()
                        self.resetbuffer()

            except KeyboardInterrupt:
                self.write('\nKeyboardInterrupt\n')
                self.resetbuffer()
                more = 0

    def push(self, line):
        self.buffer.append(line.rstrip())
        source = '\n'.join(self.buffer)

        if source.strip():
            source = re.sub('^yield ', '', source)
            match = re.match('^(\w+) = yield ', source)

            if match:
                variable = match.group(1)
                source = re.sub('^(\w+) = yield ', '', source)
            else:
                variable = None

            key_words = (
                'import',
                'from',
                '@',
                'def ',
                'if ',
                'elif',
                'else',
                'for ',
                'while',
                '#',
                'raise',
                'del',
            )
            if source.lstrip().startswith(key_words):
                r_source = source
            else:
                r_source = '_ = ' + source

            with StackContext(lambda: RequestLocals(default_actor=ACTOR_UNRESTRICTED)):
                more = self.runsource(r_source, self.filename)
        else:
            more = False

        if not more:
            result = self.locals['_']

            if is_future(result):
                @gen.coroutine
                def wait():
                    return (yield result)

                self.locals['_'] = result = ioloop.run_sync(wait)

                if variable:
                    self.locals[variable] = result

            if self.buffer[-1].strip() and result is not None:
                pprint.pprint(result)

            self.resetbuffer()

        return more

    def raw_input(self, prompt=''):
        return input(prompt)


def interact(banner=None, readfunc=None, local=None):
    console = InteractiveConsole(local)

    if readfunc is not None:
        console.raw_input = readfunc
    else:
        try:
            import readline
        except ImportError:
            pass

    console.interact(banner)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    # parser.add_argument('-q', action='store_true', help="don't print version and copyright messages")
    args = parser.parse_args()
    ioloop = IOLoop.current()
    Model.init(settings.DATABASES)
    ioloop.run_sync(Tab.update_cache)
    ioloop.run_sync(BusinessType.update_cache)
    readline.parse_and_bind('tab: complete')
    interact('C300 Shell BETA — use at your own risk!')
