# Copyright (c) CCP 2011
"""
Contains a jessica version of the space scene render job.
"""

from . import _trinity as trinity
from . import _singletons
from .sceneRenderJobSpace import SceneRenderJobSpace
import evegraphics.settings as gfxsettings


def CreateJessicaSpaceRenderJob(name=None):
    """
    We can't use __init__ on a decorated class, so we provide a creation function that does it for us
    """
    newRJ = SceneRenderJobSpaceJessica()
    if name is not None:
        newRJ.ManualInit(name)
    else:
        newRJ.ManualInit()
    return newRJ


# noinspection PyAttributeOutsideInit
class SceneRenderJobSpaceJessica(SceneRenderJobSpace):
    """ Jessica/Maya version of the space render job. """
    def _ManualInit(self, name="SceneRenderJobSpace"):
        SceneRenderJobSpace._ManualInit(self, name)
        self.persistedPostProcess = {}
        self.settings = {
            "aaQuality": 3,
            "postProcessingQuality": 2,
            "shadowQuality": 2,
            "shadowMapSize": 1024,
            "taa": False,
            "reflections": gfxsettings.GFX_REFLECTION_QUALITY_HIGHEST,
            "ao": gfxsettings.GFX_AO_QUALITY_HIGH,
            "fsr": gfxsettings.GFX_FSR_MODE_OFF
        }
        self.backBufferOverride = None
        self.depthBufferOverride = None

    def SetSettings(self, rjSettings):
        self.settings = rjSettings

    def GetSettings(self):
        return self.settings

    def GetMSAATypeFromQuality(self, quality):
        if quality == 0:
            return 0
        msaaTypes = [0]
        # Not all cards support MSAA with hdr so we have to check for that.
        fmt = trinity.PIXEL_FORMAT.R16G16B16A16_FLOAT if self.hdrEnabled else self.bbFormat

        def Supported(msType):
            return _singletons.adapters.GetRenderTargetMsaaSupport(_singletons.device.adapter, fmt, msType)

        if Supported(2):
            msaaTypes.append(2)
        if Supported(4):
            msaaTypes.append(4)
        if Supported(8):
            msaaTypes.append(8)
        elif Supported(6):
            msaaTypes.append(6)

        if quality >= len(msaaTypes):
            quality = len(msaaTypes) - 1

        return msaaTypes[quality]

    def _RefreshAntiAliasing(self):
        self.EnableMSAA(self.antiAliasingEnabled)

    def _GetSettings(self):
        """ See SceneRenderJobSpace._GetSettings """
        return self.settings

    def OverrideBuffers(self, backBuffer, depthBuffer):
        """ Overrides default backbuffer and depthbuffer """
        self.backBufferOverride = backBuffer
        self.depthBufferOverride = depthBuffer

    def _SetSettingsBasedOnPerformancePreferences(self):
        self.aaQuality = self.settings["aaQuality"]
        self.antiAliasingEnabled = self.aaQuality > 0
        self.msaaType = self.GetMSAATypeFromQuality(self.aaQuality)
        
        self.taaEnabled = self.settings.get("taa", False)

        self.shadowQuality = self.settings["shadowQuality"]
        if self.shadowQuality > 0 and self.shadowMap is None:
            self.shadowMap = trinity.TriShadowMap()
            self.shadowMap.size = self.settings["shadowMapSize"]
        elif self.shadowQuality == 0:
            self.shadowMap = None
        else:
            self.shadowMap.size = self.settings["shadowMapSize"]

    def _RefreshRenderTargets(self):
        SceneRenderJobSpace._RefreshRenderTargets(self)

        if self.depthBufferOverride:
            self.AddStep("SET_SWAPCHAIN_DEPTH", trinity.TriStepPushDepthStencil(self.depthBufferOverride))
            self.AddStep("RESET_SWAPCHAIN_DEPTH", trinity.TriStepPopDepthStencil())

        if self.backBufferOverride:
            self.AddStep("SET_SWAPCHAIN_RT", trinity.TriStepPushRenderTarget(self.backBufferOverride))
            self.AddStep("RESET_SWAPCHAIN_RT", trinity.TriStepPopRenderTarget())

    def GetBackBufferSize(self):
        """
        Gets the size of the BackBuffer of the renderjob
        """
        if self.backBufferOverride is None:
            return SceneRenderJobSpace.GetBackBufferSize(self)
        
        width = self.backBufferOverride.width
        height = self.backBufferOverride.height
        return int(width * self.invBackBufferScale), int(height * self.invBackBufferScale)

    def GetBackBufferRenderTarget(self):
        """
        Gets the BackBufferRenderTarget based on the renderContext or swapchain
        """
        if self.backBufferOverride is not None:
            return self.backBufferOverride

        return SceneRenderJobSpace.GetBackBufferRenderTarget(self)
