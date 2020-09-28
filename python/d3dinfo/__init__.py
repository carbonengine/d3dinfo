# Copyright (c) CCP 2006

"""
An indirection point so that we can switch in different flavors
of our trinity DLLs when people execute 'import trinity'.
This is also where we try to establish a proper startup environment
for trinity (D3D versions, etc).

Importing trinity in a server or proxy ExeFile will raise a RuntimeError,
not an ImportError, because we want it to be more severe.
"""

import logging
import sys
import pytelemetry.zoning as telemetry
import walk
import uthread2
import os

try:
    import blue
except ImportError:
    import binbootstrapper
    binbootstrapper.update_binaries(__file__, binbootstrapper.DLL_BLUE, binbootstrapper.DLL_TRINITY)
    import blue

import _utils

# This logic must come before the availablePlatforms import
_utils.AssertNotOnProxyOrServer()

from . import availablePlatforms
from ._singletons import *
from ._trinity import *
from .renderJob import CreateRenderJob
from .renderJobUtils import *

logger = logging.getLogger(__name__)


def GetEnumValueName(enumName, value):
    if enumName in globals():
        enum = globals()[enumName]
        result = ""
        for enumKeyName, (enumKeyValue, enumKeydocString) in enum.values.iteritems():
            if enumKeyValue == value:
                if result != "":
                    result += " | "
                result += enumKeyName
 
        return result
 

def GetEnumValueNameAsBitMask(enumName, value):
    if enumName in globals():
        enum = globals()[enumName]
        result = ""
        for enumKeyName, (enumKeyValue, enumKeydocString) in enum.values.iteritems():
            if (enumKeyValue & value) == enumKeyValue:
                if result != "":
                    result += " | "
                result += enumKeyName
 
        return result


def ConvertTriFileToGranny(path):
    helper = TriGeometryRes()
    return helper.ConvertTriFileToGranny(path)


def LoadDone(evt):
    evt.isDone = True


def WaitForResourceLoads():
    blue.resMan.Wait()
    

def WaitForUrgentResourceLoads():
    blue.resMan.WaitUrgent()
    

def LoadUrgent(path):
    blue.resMan.SetUrgentResourceLoads(True)
    obj = Load(path)
    blue.resMan.SetUrgentResourceLoads(False)
    return obj


def GetResourceUrgent(path, extra = ""):
    blue.resMan.SetUrgentResourceLoads(True)
    obj = blue.resMan.GetResource(path, extra)
    blue.resMan.SetUrgentResourceLoads(False)
    return obj


def Save(obj, path):
    blue.motherLode.Delete(path)
    return blue.resMan.SaveObject(obj, path)


def SaveRenderTarget(filename, rt=None):
    """
    Saves render target to file.
    Agruments:
    filename - OS path to file
    rt - (optional) Tr2RenderTarget to save, if None then back buffer is saved.
    """
    if rt is None:
        rt = device.GetRenderContext().GetDefaultBackBuffer()
    if not rt.isReadable:
        readable = Tr2RenderTarget(rt.width, rt.height, 1, rt.format)
        rt.Resolve(readable)
        return Tr2HostBitmap(readable).Save(filename)
    else:
        return Tr2HostBitmap(rt).Save(filename)


def _StoreGPUInfoInCrashHeaders():
    """
    Detect and save GPU information in crash headers.
    This is extremely useful for graphics crashes and required by NVidia for them to look at driver crashes
    """
    try:
        adapterInfo = adapters.GetAdapterInfo(adapters.DEFAULT_ADAPTER)

        blue.SetCrashKeyValues("GPU_Description", adapterInfo.description)
        blue.SetCrashKeyValues("GPU_Driver", adapterInfo.driver)
        blue.SetCrashKeyValues("GPU_VendorId", str(adapterInfo.vendorID))
        blue.SetCrashKeyValues("GPU_DeviceId", str(adapterInfo.deviceID))
        blue.SetCrashKeyValues("trinityPlatform", platform)
        
        try:
            driverInfo = adapterInfo.GetDriverInfo()
            blue.SetCrashKeyValues("GPU_Driver_Version", driverInfo.driverVersionString)
            blue.SetCrashKeyValues("GPU_Driver_Date", driverInfo.driverDate)
            blue.SetCrashKeyValues("GPU_Driver_Vendor", driverInfo.driverVendor)
            blue.SetCrashKeyValues("GPU_Driver_Is_Optimus", "Yes" if driverInfo.isOptimus else "No")
            blue.SetCrashKeyValues("GPU_Driver_Is_Amd_Switchable", "Yes" if driverInfo.isAmdDynamicSwitchable else "No")
        except RuntimeError:
            pass
            blue.SetCrashKeyValues("GPU_Driver_Version", str(adapterInfo.driverVersion))
    except RuntimeError:
        pass
    except SystemError:
        # TODO: A simple hack to deal with machines that can't support DX11
        if platform == "dx11":
            import log
            log.Quit("Video card may not support DX11 - setting preferred platform to DX9")


# These are helper functions which are used by eve insider and some
# jessica extensions which toggle the FPS job from time to time

def IsFpsEnabled():
    return bool("FPS" in (j.name for j in renderJobs.recurring))

def SetFpsEnabled(enable, viewPort = None):
    if enable:
        if IsFpsEnabled():
            return

        fpsJob = CreateRenderJob("FPS")
        fpsJob.SetViewport( viewPort )
        fpsJob.RenderFps()
        fpsJob.ScheduleRecurring( insertFront=False )
    
    else:
        renderJobs.UnscheduleByName("FPS")


def AddRenderJobText(text, x, y, renderJob, color = 0xFF00FF00):
    steps = [ step for step in renderJob.steps if step.name == 'RenderDebug' ]

    if len(steps) > 0:
        step = steps[0]
    else:
        return
    
    step.Print2D(x, y, color, text)
    
    return renderJob

def CreateDebugRenderJob(renderJobName, viewPort, renderJobIndex = -1):
    renderJob = CreateRenderJob( renderJobName )
         
    renderJob.SetViewport( viewPort )
    step = renderJob.RenderDebug()
    step.name = 'RenderDebug'    
    step.autoClear = False
    if renderJobIndex is -1:
        renderJob.ScheduleRecurring()       
    else :
        renderJobs.recurring.insert(renderJobIndex, renderJob)

    return renderJob


def SetupDefaultGraphs():
    graphs.Clear()
    graphs.AddGraph( 'frameTime' )
    graphs.AddGraph( 'devicePresent' )
    graphs.AddGraph( 'primitiveCount' )
    graphs.AddGraph( 'batchCount' )
    graphs.AddGraph( 'pendingLoads' )
    graphs.AddGraph( 'pendingPrepares' )
    graphs.AddGraph( 'textureResBytes' )


def AddFrameTimeMarker(name):
    line = GetLineGraphFrameTime()
    if line is not None:
        line.AddMarker( name )
              

class FrameTimeMarkerStopwatch(object):
    def __init__(self, stopwatchName):
        self.started = blue.os.GetCycles()[0]
        self.stopwatchName = stopwatchName

    def __str__(self):
        return "%s %i ms" % (self.stopwatchName, int( 1000 * ((blue.os.GetCycles()[0] - self.started) / float(blue.os.GetCycles()[1])) ))

    def __del__( self ):
        AddFrameTimeMarker( str(self) )


# Helper functions for curves, curve sets and bindings
def CreateBinding(cs, src, srcAttr, dst, dstAttr):
    binding = TriValueBinding()
    binding.sourceObject = src
    binding.sourceAttribute = srcAttr
    binding.destinationObject = dst
    binding.destinationAttribute = dstAttr
    if cs:
        cs.bindings.append( binding )
    
    return binding
    

# Helper functions for curves, curve sets and bindings
def CreatePythonBinding(cs, src, srcAttr, dst, dstAttr):
    binding = Tr2PyValueBinding()
    binding.sourceObject = src
    binding.sourceAttribute = srcAttr
    binding.destinationObject = dst
    binding.destinationAttribute = dstAttr
    if cs:
        cs.bindings.append( binding )
    
    return binding


def IsMsaaTypeSupported(msaa_type, formats):
    supported = True
    for surface_format in formats:
        args = device.adapter, surface_format[0], app.windowed, msaa_type
        try:
            if surface_format[1]:
                quality_levels = adapters.GetRenderTargetMsaaSupport(*args)
            else:
                quality_levels = adapters.GetDepthStencilMsaaSupport(*args)
        except _trinity.ALInvalidCallError:
            quality_levels = 0
        supported = supported and quality_levels
    return supported

def GetHighestSupportedMsaaType(formats):
    levels = 8, 6, 4, 2
    for each in levels:
        if IsMsaaTypeSupported(each, formats):
            return each
    return 1

def _init():
    _StoreGPUInfoInCrashHeaders()
    device.SetRenderJobs(renderJobs)

    # Create a job that calculates and displays the frames per second.
    if not blue.pyos.packaged:
        SetFpsEnabled(True)

_init()
