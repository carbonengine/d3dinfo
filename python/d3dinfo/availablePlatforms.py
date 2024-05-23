import sys
import os
import blue
import logging
logger = logging.getLogger(__name__)

try:
    d3dinfo = blue.LoadExtension("_d3dinfo")
except ImportError:
    d3dinfo = None


def IsD3D11Valid():
    """
    Returns True if Direct3D11 is available.
    """
    if not d3dinfo:
        return True

    isOK = False
    d3d = d3dinfo.D3D11Info()
    try:
        d3d.InitializeD3D()
        adapterCount = d3d.GetAdapterCount()
        if adapterCount > 0:
            isOK = True
        d3d.ShutdownD3D()
    except RuntimeError:
        pass

    return isOK


def IsD3D12Valid():
    """
    Returns True if Direct3D12 is available.
    """
    if not d3dinfo:
        return True

    isOK = False
    d3d = d3dinfo.D3D12Info()
    try:
        d3d.InitializeD3D()
        adapterCount = d3d.GetAdapterCount()
        if adapterCount > 0:
            isOK = True
        d3d.ShutdownD3D()
    except RuntimeError:
        pass

    return isOK


def GetAvailablePlatforms():
    """
    Returns a list of available platforms for Trinity.
    """
    platforms = []

    if sys.platform.startswith("darwin"):
        platforms.append("metal")
    else:
        if IsD3D11Valid():
            platforms.append("dx11")
        if IsD3D12Valid():
            platforms.append("dx12")

    platforms.append("stub")

    return platforms


def InstallSystemBinaries(fileName):
    installMsg = "Executing %s ..." % fileName
    print(installMsg)

    logger.info(installMsg)
    # Get the current working directory
    oldDir = os.getcwdu()
    # Change to the bin directory, because if the client is run from a path that contains spaces
    # in a folder name the command will fail
    os.chdir(blue.paths.ResolvePath(u"bin:/"))
    # Execute using os.system since this will wait for the process to finish.
    # This will ensure the installer is done before we check for success!
    exitStatus = os.system(fileName)
    # Switch back to the old working directory
    os.chdir(oldDir)
    # Log the results of the command. 0 -> success, 1 -> failure.
    retString = "Execution of " + fileName
    if exitStatus:
        retString += " failed (exit code %d)" % exitStatus
        logger.error(retString)
    else:
        retString += " succeeded"
        logger.info(retString)


def InstallDirectXIfNeeded():
    if not IsD3D11Valid():
        # Install appropriate redist
        import importlib.machinery
        if importlib.machinery.EXTENSION_SUFFIXES[0] == '_d.pyd':
            InstallSystemBinaries(r"DirectXRedistForDebug.exe")
        else:
            InstallSystemBinaries(r"DirectXRedist.exe")
