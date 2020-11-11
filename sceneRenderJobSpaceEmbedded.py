# Copyright (c) CCP 2011
"""
Contains and embedded version of the space scene render job.
"""
import logging

from . import _trinity as trinity
from .sceneRenderJobSpace import SceneRenderJobSpace
from .renderJob import CreateRenderJob

logger = logging.getLogger(__name__)

def CreateEmbeddedRenderJobSpace(name=None, stageKey=None,usePostProcessing=True):
    """
    We can't use __init__ on a decorated class, so we provide a creation function that does it for us
    """
    newRJ = SceneRenderJobSpaceEmbedded()
    if name is not None:
        newRJ.ManualInit(name)
    else:
        newRJ.ManualInit()

    newRJ.embeddedPostprocessing = usePostProcessing

    newRJ.SetMultiViewStage(stageKey)
    return newRJ


class SceneRenderJobSpaceEmbedded(SceneRenderJobSpace):
    """
    SceneRenderJobSpaceEmbedded is used to display space scenes in ui windows
    and such. The preview, ship fitting and cq mainscreen f.x.
    """

    renderStepOrder = [
        "PUSH_RENDER_TARGET",
        "PUSH_DEPTH_STENCIL",
    ]
    renderStepOrder += SceneRenderJobSpace.renderStepOrder
    renderStepOrder += [
        "POP_RENDER_TARGET",
        "POP_DEPTH_STENCIL",
        "COPY_TO_BLIT_TEXTURE",
        "PUSH_POSTPROCESSING_RENDER_TARGET",
        "RJ_POSTPROCESSING_EMBEDDED",
        "POP_POSTPROCESSING_RENDER_TARGET",
        "PUSH_BLIT_DEPTH",
        "SET_BLIT_VIEWPORT",
        "SET_BLENDMODE",
        "FINAL_BLIT_EMBEDDED",
        "POP_BLIT_DEPTH",
    ]

    def _ManualInit(self, name):
        self.stencilBlitEffect = None
        self.stencilPath = ""
        self.SetupStencilBlitEffect()

        self.isOffscreen = False
        self.doFinalBlit = True

        self.offscreenRenderTarget = None
        self.offscreenDepthStencil = None
        self.finalTexture = None

        self.rtWidth = 0
        self.rtHeight = 0

        self.blitViewport = trinity.TriViewport()

        SceneRenderJobSpace._ManualInit(self, name)
        self.updateJob = None
        self.useTAA = False
        self.useImpostors = False
        self.useReflectionProbe = False

        self.embeddedPostprocessing = True


    def SetupStencilBlitEffect(self):
        self.stencilBlitEffect = trinity.Tr2Effect()
        self.stencilBlitEffect.effectFilePath = "res:/Graphics/Effect/Managed/Space/system/BlitStencil.fx"

        stencilMap = trinity.TriTextureParameter()
        stencilMap.name = "StencilMap"
        stencilMap.resourcePath = self.stencilPath
        self.stencilBlitEffect.resources.append(stencilMap)

        self.blitMapParameter = trinity.TriTextureParameter()
        self.blitMapParameter.name = "BlitSource"
        self.stencilBlitEffect.resources.append(self.blitMapParameter)

    def SetOffscreen(self, isOffscreen):
        self.isOffscreen = isOffscreen

    def SetStencil(self, path=None):
        self.stencilPath = path
        self.SetupStencilBlitEffect()

        self.EnableStep("CLEAR")

        self._RefreshAntiAliasing()
        self._CreateRenderTargets()
        self._RefreshRenderTargets()

    def _DoPrepareResources(self):
        self.useDepth = trinity.GetShaderModel().endswith("DEPTH")
        self.prepared = True

        self.SetSettingsBasedOnPerformancePreferences()

    def ScheduleUpdateJob(self):
        if self.updateJob is None:
            self.updateJob = CreateRenderJob("embedded_Update")
            self.updateJob.scheduled = False
        super(SceneRenderJobSpaceEmbedded, self).ScheduleUpdateJob()

    def DoReleaseResources(self, level):
        self.finalTexture = None
        self.offscreenRenderTarget = None
        self.offscreenDepthStencil = None
        self.blitMapParameter.SetResource(None)

        SceneRenderJobSpace.DoReleaseResources(self, level)

    def DoPrepareResources(self):
        """
        This function is called when the device is restored.
        This function may raise exceptions attempting to create resources!
        NB: Will need to be changed to allow other sources to provide the buffers
        """
        if not self.enabled or not self.canCreateRenderTargets:
            return

        try:
            self._DoPrepareResources()
        except trinity.D3DERR_OUTOFVIDEOMEMORY:
            log.LogException()
            self.DoReleaseResources(1)

    def _GetSourceRTForPostProcessing(self):
        if self.msaaEnabled or self.hdrEnabled:
            return self.customBackBuffer
        return self.finalTexture

    def _CreateRenderTargets(self):
        if not self.prepared:
            return

        SceneRenderJobSpace._CreateRenderTargets(self)

        vp = self.GetViewport()

        self.rtWidth = vp.width
        self.rtHeight = vp.height

        if self.customBackBuffer is None:
            self.offscreenRenderTarget = trinity.Tr2RenderTarget(
                vp.width, vp.height, 1, self.bbFormat)
            self.finalTexture = self.offscreenRenderTarget
        else:
            self.finalTexture = trinity.Tr2RenderTarget(vp.width, vp.height, 1, self.customBackBuffer.format)


        if self.customDepthStencil is None:
            self.offscreenDepthStencil = trinity.Tr2DepthStencil(
                vp.width, vp.height, trinity.DEPTH_STENCIL_FORMAT.AUTO)

        self.finalTexture.name = 'finalTexture'


    def _UsePostProcessingEmbedded(self):
        return self.usePostProcessing and self.embeddedPostprocessing

    def SetRenderTargets(self, *args):
        SceneRenderJobSpace.SetRenderTargets(self, *args)

        self.RemoveStep("PUSH_RENDER_TARGET")
        self.RemoveStep("PUSH_DEPTH_STENCIL")
        self.RemoveStep("POP_RENDER_TARGET")
        self.RemoveStep("POP_DEPTH_STENCIL")
        self.RemoveStep("SET_BLIT_VIEWPORT")
        self.RemoveStep("COPY_TO_BLIT_TEXTURE")
        self.RemoveStep("FINAL_BLIT_EMBEDDED")
        self.RemoveStep("PUSH_BLIT_DEPTH")
        self.RemoveStep("POP_BLIT_DEPTH")
        self.RemoveStep("PUSH_POSTPROCESSING_RENDER_TARGET")
        self.RemoveStep("RJ_POSTPROCESSING_EMBEDDED")
        self.RemoveStep("POP_POSTPROCESSING_RENDER_TARGET")

        viewport = self.GetViewport()

        if viewport is not None:
            vpStep = self.GetStep('SET_VIEWPORT')
            if vpStep is not None:
                vpOrigin = trinity.TriViewport(0, 0, viewport.width, viewport.height)
                vpStep.viewport = vpOrigin
                self._SetUpdateStep(vpStep, "SET_VIEWPORT")

        if self.offscreenDepthStencil:
            self.AddStep("PUSH_DEPTH_STENCIL", trinity.TriStepPushDepthStencil(self.offscreenDepthStencil))
            self.AddStep("POP_DEPTH_STENCIL", trinity.TriStepPopDepthStencil())

        if self.offscreenRenderTarget:
            self.AddStep("PUSH_RENDER_TARGET", trinity.TriStepPushRenderTarget(self.offscreenRenderTarget))
            self.AddStep("POP_RENDER_TARGET", trinity.TriStepPopRenderTarget())

        self.AddStep("PUSH_BLIT_DEPTH", trinity.TriStepPushDepthStencil(None))
        self.RemoveStep("FINAL_BLIT")


        if self._UsePostProcessingEmbedded():
            self.AddStep("RJ_POSTPROCESSING_EMBEDDED",trinity.TriStepRenderPostProcess(self.GetScene(), self._GetSourceRTForPostProcessing()))

            if self.finalTexture:
                self.AddStep("PUSH_POSTPROCESSING_RENDER_TARGET",trinity.TriStepPushRenderTarget(self.finalTexture))
                self.AddStep("POP_POSTPROCESSING_RENDER_TARGET", trinity.TriStepPopRenderTarget())

        if self.customBackBuffer is not None and self.finalTexture is not None:
            step = trinity.TriStepResolve(self.finalTexture, self.customBackBuffer)
            step.name = 'Resolve: finalTexture <== customBackBuffer'
            self.AddStep("COPY_TO_BLIT_TEXTURE", step)

        if self.doFinalBlit:
            self.AddStep("SET_BLIT_VIEWPORT", trinity.TriStepSetViewport(viewport))

            if self.finalTexture:
                if self.stencilPath is None or self.stencilPath == "":
                    self.AddStep("FINAL_BLIT_EMBEDDED", trinity.TriStepRenderTexture(self.finalTexture))
                else:
                    self.blitMapParameter.SetResource(self.finalTexture)
                    self.AddStep("FINAL_BLIT_EMBEDDED", trinity.TriStepRenderEffect(self.stencilBlitEffect))

        self.AddStep("POP_BLIT_DEPTH", trinity.TriStepPopDepthStencil())

    def GetBackBufferSize(self):
        vp = self.GetViewport()
        return vp.width, vp.height

    def DoFinalBlit(self, enabled):
        self.doFinalBlit = enabled

    def UpdateViewport(self, viewport):

        if viewport.width != self.rtWidth or viewport.height != self.rtHeight:
            self._CreateRenderTargets()
            self._RefreshRenderTargets()

    def _GetRTForDepthPass(self):
        if self.finalTexture is not None:
            return self.finalTexture

        return SceneRenderJobSpace._GetRTForDepthPass(self)

    def ApplyBaseSettings(self):
        SceneRenderJobSpace.ApplyBaseSettings(self)
        self.gpuParticlesEnabled = False
