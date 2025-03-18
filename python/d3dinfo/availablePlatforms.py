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


# List of Intel on-board GPU device IDs that are D3D12 capable on paper
# IDs are taken from https://dgpu-docs.intel.com/devices/hardware-table.html
_INTEL_ONBOARD_DEVICE_IDS = [
    0xA780,  # Intel UHD Graphics 770 Xe Raptor Lake-S 5.17 32
    0xA781, 0xA788, 0xA789,  # Intel UHD Graphics Xe Raptor Lake-S 5.17 32
    0xA78A,  # Intel UHD Graphics Xe Raptor Lake-S 5.19 24
    0xA782,  # Intel UHD Graphics 730 Xe Raptor Lake-S 5.17 24
    0xA78B,  # Intel UHD Graphics Xe Raptor Lake-S 5.19 16
    0xA783,  # Intel UHD Graphics 710 Xe Raptor Lake-S 5.17 16
    0xA7A0, 0xA7A1,  # Intel Iris Xe Graphics Xe Raptor Lake-P 5.19 96/80
    0xA7A8,  # Intel UHD Graphics Xe Raptor Lake-P 5.19 64/48
    0xA7AA,  # Intel Graphics Xe Raptor Lake-P 6.7 96/80
    0xA7AB,  # Intel Graphics Xe Raptor Lake-P 6.7 64/48
    0xA7AC,  # Intel Graphics Xe Raptor Lake-U 6.7 96/80
    0xA7AD,  # Intel Graphics Xe Raptor Lake-U 6.7 64/48
    0xA7A9,  # Intel UHD Graphics Xe Raptor Lake-P 5.19 64/48
    0xA721,  # Intel UHD Graphics Xe Raptor Lake-P 5.19 96/80
    0x4905,  # Intel Iris Xe MAX Graphics Xe DG1 5.16* 96
    0x4907,  # Intel Server GPU SG-18M Xe DG1 5.16* 96
    0x4908,  # Intel Iris Xe Graphics Xe DG1 5.16* 80
    0x4909,  # Intel Iris Xe MAX 100 Graphics Xe DG1 5.16* 80
    0x4680, 4690,  # Intel UHD Graphics 770 Xe Alder Lake-S 5.16 32
    0x4688,  # Intel UHD Graphics 770 Xe Alder Lake-S 5.16 32
    0x468A,  # Intel UHD Graphics 770 Xe Alder Lake-S 5.16 24
    0x468B,  # Intel UHD Graphics 770 Xe Alder Lake-S 6.1 16
    0x4682, 4692,  # Intel UHD Graphics 730 Xe Alder Lake-S 5.16 24
    0x4693,  # Intel UHD Graphics 710 Xe Alder Lake-S 5.16 16
    0x46D3,  # Intel Graphics Xe Alder Lake-N 6.9 32
    0x46D4,  # Intel Graphics Xe Alder Lake-N 6.9 24
    0x46D0,  # Intel UHD Graphics Xe Alder Lake-N 5.18 32
    0x46D1,  # Intel UHD Graphics Xe Alder Lake-N 5.18 24
    0x46D2,  # Intel UHD Graphics Xe Alder Lake-N 5.18 16
    0x4626, 0x4628, 0x462A,  # Intel UHD Graphics Xe Alder Lake-P 5.17 96/80
    0x46A2, 0x46B3, 0x46C2,  # Intel UHD Graphics Xe Alder Lake-P 5.17 64
    0x46A3, 0x46B2, 0x46C3,  # Intel UHD Graphics Xe Alder Lake-P 5.17 64/48
    0x46A0, 0x46B0, 0x46C0,  # Intel Iris Xe Graphics Xe Alder Lake-P 5.17 96
    0x46A6, 0x46AA, 0x46A8,  # Intel Iris Xe Graphics Xe Alder Lake-P 5.17 96/80
    0x46A1, 0x46B1, 0x46C1,  # Intel Iris Xe Graphics Xe Alder Lake-P 5.17 80
    0x4C8A,  # Intel UHD Graphics 750 Xe Rocket Lake 5.13 32
    0x4C8B,  # Intel UHD Graphics 730 Xe Rocket Lake 5.13 24
    0x4C90, 0x4C9A,  # Intel UHD Graphics P750 Xe Rocket Lake 5.13 24
    0x4E71,  # Intel UHD Graphics Xe Jasper Lake 5.15 32
    0x4E61,  # Intel UHD Graphics Xe Jasper Lake 5.15 24
    0x4E57,  # Intel UHD Graphics Xe Jasper Lake 5.15 20
    0x4E55,  # Intel UHD Graphics Xe Jasper Lake 5.15 16
    0x4E51,  # Intel UHD Graphics Xe Jasper Lake 5.15 16
    0x4557,  # Intel UHD Graphics Xe Elkhart Lake 5.15 20
    0x4555,  # Intel UHD Graphics Xe Elkhart Lake 5.15 16
    0x4571,  # Intel UHD Graphics Xe Elkhart Lake 5.15 32
    0x4551,  # Intel UHD Graphics Xe Elkhart Lake 5.15 16
    0x4541,  # Intel UHD Graphics Xe Elkhart Lake 5.15 8
    0x9A59,  # Intel UHD Graphics Xe Tiger Lake 5.7 96
    0x9A78,  # Intel UHD Graphics Xe Tiger Lake 5.7 48
    0x9A60, 0x9A70,  # Intel UHD Graphics Xe Tiger Lake 5.7 32
    0x9A68,  # Intel UHD Graphics Xe Tiger Lake 5.7 16
    0x9A40, 0x9A49,  # Intel Iris Xe Graphics Xe Tiger Lake 5.7 96/80

    0x8A70, 0x8A71,  # Intel HD Graphics Gen11 Ice Lake 5.10
    0x8A56, 0x8A58,  # Intel UHD Graphics Gen11 Ice Lake 5.10
    0x8A5B, 0x8A5D,  # Intel HD Graphics Gen11 Ice Lake 5.10
    0x8A54, 0x8A5A, 0x8A5C,  # Intel Iris Plus Graphics Gen11 Ice Lake 5.10
    0x8A57, 0x8A59,  # Intel HD Graphics Gen11 Ice Lake 5.10
    0x8A50,  # Intel HD Graphics Gen11 Ice Lake 5.10
    0x8A51, 0x8A52, 0x8A53,  # Intel Iris Plus Graphics Gen11 Ice Lake 5.10
    0x3EA5, 0x3EA8,  # Intel Iris Plus Graphics 655 Gen9 Coffee Lake 5.10
    0x3EA6,  # Intel Iris Plus Graphics 645 Gen9 Coffee Lake 5.10
    0x3EA7,  # Intel HD Graphics Gen9 Coffee Lake 5.10
    0x3EA2,  # Intel UHD Graphics Gen9 Coffee Lake 5.10
    0x3E90, 0x3E93, 0x3E99, 0x3E9C, 0x3EA1, 0x9BA5, 0x9BA8,  # Intel UHD Graphics 610 Gen9 Coffee Lake 5.10
    0x3EA4, 0x9B21, 0x9BA0, 0x9BA2, 0x9BA4, 0x9BAA, 0x9BAB, 0x9BAC,  # Intel UHD Graphics Gen9 Coffee Lake 5.10
    0x87CA, 0x3EA3, 0x9B41, 0x9BC0, 0x9BC2, 0x9BC4, 0x9BCA, 0x9BCB, 0x9BCC,  # Intel UHD Graphics Gen9 Coffee Lake 5.10
    0x3E91, 0x3E92, 0x3E98, 0x3E9B, 0x9BC5, 0x9BC8,  # Intel UHD Graphics 630 Gen9 Coffee Lake 5.10
    0x3E96, 0x3E9A, 0x3E94, 0x9BC6, 0x9BE6, 0x9BF6,  # Intel UHD Graphics P630 Gen9 Coffee Lake 5.10
    0x3EA9, 0x3EA0,  # Intel UHD Graphics 620 Gen9 Coffee Lake 5.10
    0x593B,  # Intel HD Graphics Gen9 Kaby Lake 5.10
    0x5923,  # Intel HD Graphics 635 Gen9 Kaby Lake 5.10
    0x5926,  # Intel Iris Plus Graphics 640 Gen9 Kaby Lake 5.10
    0x5927,  # Intel Iris Plus Graphics 650 Gen9 Kaby Lake 5.10
    0x5917,  # Intel UHD Graphics 620 Gen9 Kaby Lake 5.10
    0x5912, 0x591B,  # Intel HD Graphics 630 Gen9 Kaby Lake 5.10
    0x5916, 0x5921,  # Intel HD Graphics 620 Gen9 Kaby Lake 5.10
    0x591A, 0x591D,  # Intel HD Graphics P630 Gen9 Kaby Lake 5.10
    0x591E,  # Intel HD Graphics 615 Gen9 Kaby Lake 5.10
    0x591C,  # Intel UHD Graphics 615 Gen9 Kaby Lake 5.10
    0x87C0,  # Intel UHD Graphics 617 Gen9 Kaby Lake 5.10
    0x5913, 0x5915,  # Intel HD Graphics Gen9 Kaby Lake 5.10
    0x5902, 0x5906, 0x590B,  # Intel HD Graphics 610 Gen9 Kaby Lake 5.10
    0x590A, 0x5908, 0x590E,  # Intel HD Graphics Gen9 Kaby Lake 5.10
    0x3185,  # Intel UHD Graphics 600 Gen9 Gemini Lake 5.10
    0x3184,  # Intel UHD Graphics 605 Gen9 Gemini Lake 5.10
    0x1A85,  # Intel HD Graphics Gen9 Apollo Lake 5.10
    0x5A85,  # Intel HD Graphics 500 Gen9 Apollo Lake 5.10
    0x0A84, 0x1A84,  # Intel HD Graphics Gen9 Apollo Lake 5.10
    0x5A84,  # Intel HD Graphics 505 Gen9 Apollo Lake 5.10
    0x192A,  # Intel HD Graphics Gen9 Skylake 5.11
    0x1932, 0x193B,  # Intel Iris Pro Graphics 580 Gen9 Skylake 5.10
    0x193A, 0x193D,  # Intel Iris Pro Graphics P580 Gen9 Skylake 5.10
    0x1923,  # Intel HD Graphics 535 Gen9 Skylake 5.10
    0x1926,  # Intel Iris Graphics 540 Gen9 Skylake 5.10
    0x1927,  # Intel Iris Graphics 550 Gen9 Skylake 5.10
    0x192B,  # Intel Iris Graphics 555 Gen9 Skylake 5.10
    0x192D,  # Intel Iris Graphics P555 Gen9 Skylake 5.10
    0x1912, 0x191B,  # Intel HD Graphics 530 Gen9 Skylake 5.10
    0x1913, 0x1915, 0x1917, 0x191A,  # Intel HD Graphics Gen9 Skylake 5.10
    0x1916, 0x1921,  # Intel HD Graphics 520 Gen9 Skylake 5.10
    0x191D,  # Intel HD Graphics P530 Gen9 Skylake 5.10
    0x191E,  # Intel HD Graphics 515 Gen9 Skylake 5.10
    0x1902, 0x1906, 0x190B,  # Intel HD Graphics 510 Gen9 Skylake 5.10
    0x190A, 0x190E,  # Intel HD Graphics Gen9 Skylake 5.10

    0x163D, 0x163A, 0x1632, 0x163E, 0x163B, 0x1636,  # Intel HD Graphics Gen8 Broadwell 5.10
    0x1622,  # Intel Iris Pro Graphics 6200 Gen8 Broadwell 5.10
    0x1626,  # Intel HD Graphics 6000 Gen8 Broadwell 5.10
    0x162A,  # Intel Iris Pro Graphics P6300 Gen8 Broadwell 5.10
    0x162B,  # Intel Iris Graphics 6100 Gen8 Broadwell 5.10
    0x162D, 0x162E,  # Intel HD Graphics Gen8 Broadwell 5.10
    0x1612,  # Intel HD Graphics 5600 Gen8 Broadwell 5.10
    0x1616,  # Intel HD Graphics 5500 Gen8 Broadwell 5.10
    0x161A,  # Intel HD Graphics P5700 Gen8 Broadwell 5.10
    0x161B, 0x161D,  # Intel HD Graphics Gen8 Broadwell 5.10
    0x161E,  # Intel HD Graphics 5300 Gen8 Broadwell 5.10
    0x1602, 0x1606, 0x160A, 0x160B, 0x160D, 0x160E,  # Intel HD Graphics Gen8 Broadwell 5.10
    0x22B0, 0x22B2, 0x22B3,  # Intel HD Graphics Gen8 Cherryview 5.10
    0x22B1,  # Intel HD Graphics XXX Gen8 Cherryview 5.10
]

_INTEL_VENDOR_ID = 32902


def IsIntelOnBoardGpu(adapterInfo):
    """
    Returns True if the adapter is an Intel on-board GPU.
    """
    return adapterInfo.vendorID == _INTEL_VENDOR_ID and adapterInfo.deviceID in _INTEL_ONBOARD_DEVICE_IDS


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
            # Old Intel on-board GPUs are not capable of running with Trinity on D3D12
            try:
                if IsIntelOnBoardGpu(d3d.GetAdapterInfo(0)):
                    logger.info("Intel on-board GPU detected, assuming D3D12 is not supported")
                    isOK = False
            except:
                pass
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
    print installMsg

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
        import imp
        if imp.get_suffixes()[0][0] == '_d.pyd':
            InstallSystemBinaries(r"DirectXRedistForDebug.exe")
        else:
            InstallSystemBinaries(r"DirectXRedist.exe")
