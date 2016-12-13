"""
Python module for importing and exposing types from the trinity dll/pyd.
"""

# This stuff used to live in trinity/__init__.py
# but a lot of modules that were imported in __init__.py were using it
# creating weird circular dependencies and some strange behaviour.

import logging as _logging
import os as _os
import sys as _sys

import blue as _blue


# This is a hack to allow PyCharm to parse stub files for trinity. The _trinity_dx11_internal_stub stub is located
# in packages/stubgen/stubs and will always generate an ImportError.
try:
    from _trinity_dx11_internal_stub import *
except ImportError:
    pass

_logger = _logging.getLogger('trinity')

from . import availablePlatforms, _utils

if _blue.pyos.packaged:
    DEFAULT_TRI_PLATFORM = "dx11"
    DEFAULT_TRI_TYPE = "deploy"
    VALID_TRI_TYPES = ["deploy"]
else:
    if _sys.platform.startswith("linux") or _sys.platform.startswith("darwin"):
        DEFAULT_TRI_PLATFORM = "gles2"
    else:
        DEFAULT_TRI_PLATFORM = "dx11"
    DEFAULT_TRI_TYPE = "internal"
    VALID_TRI_TYPES = ["deploy", "internal", "dev"]


def _RobustImport(moduleName, moduleNameForFallback=None):
    """
    Method for importing trinity DLL, with an optional fallback if import fails
    """
    try:
        mod = __import__(moduleName, fromlist=['*'])
    except ImportError as ex:
        # Try fallback module if provided
        if moduleNameForFallback:
            print "Import failed on %s, falling back to %s ..." % (
                moduleName, moduleNameForFallback)
            mod = __import__(moduleNameForFallback, fromlist=['*'])
        else:
            _utils.Quit("Failed to import trinity DLL (%r)" % ex)

    for memberName in dir(mod):
        globals()[memberName] = getattr(mod, memberName)
    del mod

def _ImportDll():
    """
    Imports the Trinity dll, selecting version to use based on command line arguments.
    Returns the platform selected.
    """
    triPlatform = _os.getenv("TRINITYPLATFORM", DEFAULT_TRI_PLATFORM)
    triType = _os.getenv("TRINITYTYPE", DEFAULT_TRI_TYPE)
    disablePlatformCheck = _os.getenv("TRINITYNOPLATFORMCHECK")

    for arg in _blue.pyos.GetArg():
        arg = arg.lower()

        if arg.startswith("/triplatform"):
            s = arg.split("=")
            triPlatform = s[1]

        elif arg.startswith("/tritype"):
            s = arg.split("=")
            triType = s[1]

        elif arg == "/no-platform-check":
            disablePlatformCheck = True

    if triType not in VALID_TRI_TYPES:
        import log
        log.Quit("Invalid Trinity dll type")

    if not disablePlatformCheck:
        if triPlatform.startswith("dx"):
            availablePlatforms.InstallDirectXIfNeeded()

        validPlatforms = availablePlatforms.GetAvailablePlatforms()
        if triPlatform not in validPlatforms:
            _logger.warn("Invalid Trinity platform %s" % triPlatform)
            triPlatform = validPlatforms[0]
            _logger.info("Using Trinity platform %s instead" % triPlatform)
    else:
        _logger.info("Skipping platform check")

    dllName = "_trinity_%s_%s" % (triPlatform, triType)
    print "Starting up Trinity through %s ..." % dllName
    _RobustImport(dllName)

    if hasattr(_blue, "memoryTracker") and hasattr(_blue.memoryTracker, "d3dHeap1"):
        if GetD3DCreatedHeapCount() > 0:
            _blue.memoryTracker.d3dHeap1 = GetD3DCreatedHeap(0)
        if GetD3DCreatedHeapCount() > 1:
            _blue.memoryTracker.d3dHeap2 = GetD3DCreatedHeap(1)

    return triPlatform


def Load(path, nonCached = False):
    if nonCached:
        _blue.resMan.loadObjectCache.Delete(path)
    obj = _blue.resMan.LoadObject(path)
    return obj
