import sys
import blue
from eveprefs import boot


def Quit(msg):
    try:
        import log
        log.Quit(msg)
    except ImportError:
        sys.stderr.write(msg + '\n')
        sys.exit(4)


def AssertNotOnProxyOrServer():
    try:
        cmdlineargs = blue.pyos.GetArg()
        if bot is not None and boot.role in ("server", "proxy") and "/jessica" not in cmdlineargs and "/minime" not in cmdlineargs:
            raise RuntimeError("Don't import trinity on the proxy or server")
    except NameError:
        pass