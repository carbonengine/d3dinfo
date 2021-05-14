import evegraphics.settings as gfxsettings

from .sceneRenderJobBase import SceneRenderJobBase
from .renderJobUtils import renderTargetManager as rtm
from . import _singletons
from . import _trinity as trinity
import trinity.evePostProcess
import charactercreator.client.grading as grading
# paperDoll is imported later on, wth!



def CreateSceneRenderJobCharacters(name=None):
    """
    We can't use __init__ on a decorated class, so we provide a creation function that does it for us
    """
    newRJ = SceneRenderJobCharacters()
    if name is not None:
        newRJ.ManualInit(name)
    else:
        newRJ.ManualInit()
    return newRJ


class SceneRenderJobCharacters(SceneRenderJobBase):
    """
    This is a renderjob manager for creating and managing the renderjob to forwards 
    render characters, both ingame and in Jessica.
    """

    # This is a master list that we can refer to, when we want to insert steps that are not already in
    # the render steps, by looking for the prior or next step that exists, in order to position the new one
    # See: AddStep
    renderStepOrder = [
        "UPDATE_SCENE",
        "UPDATE_UI",
        "UPDATE_BACKDROP",
        "UPDATE_CAMERA",
        "UPDATE_SECONDARY_CAMERAS",
        "SET_BG_LAYER",
        "SET_BACKBUFFER",
        "SET_DEPTH_STENCIL",
        "SET_VIEWPORT",
        "CLEAR",
        "SET_PROJECTION",
        "SET_VIEW",
        "SCATTER",
        "RENDER_BACKDROP",
        "RENDER_SCENE",
        "RENDER_SCULPTING",  # This is actually a sub-renderjob
        "RESTORE_BACKBUFFER",
        "RESTORE_DEPTH_STENCIL",
        "RESOLVE_IMAGE",
        "RJ_POSTPROCESSING",
        "SET_BLITCURRENT",
        "SET_BLITORIGINAL",
        "RENDER_BLEND",
        "RENDER_TOOLS",
        "RENDER_UI",
    ]

    def setupPostProcess(self):
        resolveTarget = self.GetBackBufferRenderTarget()
        self.resolveTargetDimensions = (resolveTarget.width, resolveTarget.height)
        if self.postProcess is None:
            self.postProcess = grading.PostProcess('res:/dx9/scene/postprocess/portraitLUT.red', resolveTarget, viewport=self.viewport)
            self.AddStep("RJ_POSTPROCESSING", trinity.TriStepRunJob(self.postProcess.GetJob()))
        lut = grading.GetTexLUT(self)
        if lut is not None:
            lut.resourcePath = self.lut_res_path

    def UpdatePostProcessingTexCoords(self):
        if self.postProcess is not None:
            step = grading.GetLUTStepRenderEffect(self.postProcess.GetJob())
            texcoords = None
            if hasattr(self, "viewport") and hasattr(self, 'resolveTargetDimensions') and step is not None and self.viewport is not None and self.viewport.object is not None:
                texcoords_top = float(self.viewport.object.y) / self.resolveTargetDimensions[1]
                texcoords_left = float(self.viewport.object.x) / self.resolveTargetDimensions[0]
                texcoords_bottom = float(self.viewport.object.y + self.viewport.object.height) / self.resolveTargetDimensions[1]
                texcoords_right = float(self.viewport.object.x + self.viewport.object.width) / self.resolveTargetDimensions[0]
                texcoords = (texcoords_left, texcoords_top, texcoords_right, texcoords_bottom)
            if texcoords is not None:
                step.tlTexCoord = (texcoords[0], texcoords[1])
                step.brTexCoord = (texcoords[2], texcoords[3])

    def _ManualInit(self, name="SceneRenderJobCharacters"):
        """
        Decorated classes cannot use a normal init function, so this must be called manually
        This version is called from ManualInit on SceneRenderJobBase
        """
        # in general most of these use weakrefs to prevent circular references
        self.scatterEnabled = False
        self.sculptingEnabled = False

        self.customBackBuffer = None
        self.customDepthStencil = None
        self.resolveBuffer = None
        self.lut_res_path = "res:/dx9/scene/postprocess/NCC_normal.dds"
        self.postProcess = None
        self.startOpacity = 1.0
        self.dx9_active = trinity.platform == "dx9"
        self.releasing = False
        self.rebuilding = False

    def _SetScene(self, scene):
        """
        Sets a scene into the render job
        """
        self.SetStepAttr("UPDATE_SCENE", 'object', scene)
        self.SetStepAttr("RENDER_SCENE", 'scene', scene)

    def _CreateBasicRenderSteps(self):
        # This will clear the current steps
       
        # Create approximately the most basic renderjob setup
        # Assuming that someone wanted to use multiple versions of these together, then
        # they would need to disable "CLEAR_PREPASS" and "CLEAR_LIGHTS", while sharing the render targets with the other steps
        self.AddStep("UPDATE_SCENE", trinity.TriStepUpdate(self.GetScene()))
        self.AddStep("CLEAR", trinity.TriStepClear((0.0, 0.0, 0.0, 0.0), 1.0))
        self.AddStep("RENDER_SCENE", trinity.TriStepRenderScene(self.GetScene()))
            
    def DoReleaseResources(self, level):
        """
        This function is called when the device is lost.
        """

        self.customBackBuffer = None
        self.customDepthStencil = None
        self.resolveBuffer = None
        self.bgBuffer = None
        if self.postProcess is not None:
            self.postProcess.job.Release()


    def DoPrepareResources(self):
        """
        This function is called when the device is restored. 
        This function may raise exceptions attempting to create resources!
        """
        self.SetSettingsBasedOnPerformancePreferences()

    def SetSettingsBasedOnPerformancePreferences(self):
        if not self.enabled:
            return

        viewport = self.GetViewport()
        self.SetStepAttr("CLEAR", "isColorCleared", True)
        if self.dx9_active:
            msaaType = 1
        elif sm.IsServiceRunning("device"):
            aaQuality = gfxsettings.Get(gfxsettings.GFX_ANTI_ALIASING)
            msaaType = sm.GetService("device").GetMSAATypeFromQuality(aaQuality)
        else:
            msaaType = 4

        if msaaType <= 1:
            self.SetStepAttr("CLEAR", "isColorCleared", False)

        width, height = self.GetBackBufferSize()

        bbFormat = _singletons.device.GetRenderContext().GetBackBufferFormat()
        dsFormat = trinity.DEPTH_STENCIL_FORMAT.D24S8

        self.customBackBuffer = None
        self.customDepthStencil = rtm.GetDepthStencilAL(width, height, dsFormat, msaaType)
        self.AddStep("SET_DEPTH_STENCIL", trinity.TriStepPushDepthStencil(self.customDepthStencil))
        self.AddStep("RESTORE_DEPTH_STENCIL", trinity.TriStepPopDepthStencil())

        if viewport:
            self.bgBuffer = rtm.GetRenderTargetAL(width, height, 1, bbFormat)
            self.AddStep("SET_BG_LAYER", trinity.TriStepResolve(self.bgBuffer, self.GetBackBufferRenderTarget()))
            self.AddStep("SET_BLITORIGINAL", trinity.TriStepSetVariableStore("BlitOriginal", self.bgBuffer))
            self.setupPostProcess()
            self.AddStep("SET_BLITCURRENT", trinity.TriStepSetVariableStore("BlitCurrent", self.postProcess.GetJob().resolveTarget))
            self.AddStep("RENDER_BLEND", trinity.TriStepRenderEffect(self.CreateRenderBlendEffect(msaaType)))

        if msaaType <= 1:
            self.RemoveStep("SET_BACKBUFFER")
            self.RemoveStep("RESTORE_BACKBUFFER")
            self.RemoveStep("RESOLVE_IMAGE")
        else:
            self.customBackBuffer = rtm.GetRenderTargetMsaaAL(width, height, bbFormat, msaaType, 0)
            self.AddStep("SET_BACKBUFFER", trinity.TriStepPushRenderTarget(self.customBackBuffer))
            self.AddStep("RESTORE_BACKBUFFER", trinity.TriStepPopRenderTarget())

            self.AddStep("RESOLVE_IMAGE", trinity.TriStepResolve(self.GetBackBufferRenderTarget(), self.customBackBuffer))


    def UpdateViewport(self, new_viewport):
        if not self.customDepthStencil:
            return
        viewport = self.GetViewport()
        if viewport is None or new_viewport.width != viewport.width or new_viewport.height != viewport.height:
            self.SetSettingsBasedOnPerformancePreferences()
        else:
            self.UpdatePostProcessingTexCoords()

    def Enable(self, schedule=True):
        SceneRenderJobBase.Enable(self, schedule)
        self.EnableScatter(self.scatterEnabled)
        self.EnableSculpting(self.sculptingEnabled)

    def Disable(self):
        SceneRenderJobBase.Disable(self)
        self.EnableScatter(self.scatterEnabled)
        self.EnableSculpting(self.sculptingEnabled)

    def EnableScatter(self, isEnabled):
        from eve.client.script.paperDoll.SkinLightmapRenderer import SkinLightmapRenderer

        self.scatterEnabled = isEnabled
        if self.enabled and isEnabled:
            self.AddStep("SCATTER", SkinLightmapRenderer.CreateScatterStep(self, self.GetScene(), False))
        else:
            self.RemoveStep("SCATTER")

    def EnableSculpting(self, isEnabled):
        from eve.client.script.paperDoll.AvatarGhost import AvatarGhost

        self.sculptingEnabled = isEnabled
        if self.enabled and isEnabled:
            self.AddStep("RENDER_SCULPTING", AvatarGhost.CreateSculptingStep(self, False))
        else:
            self.RemoveStep("RENDER_SCULPTING")

    def SetCameraUpdate(self, job):
        self.AddStep("UPDATE_CAMERA", trinity.TriStepRunJob(job))

    def Set2DBackdropUIRoot(self, uiRoot):
        if uiRoot is not None:
            self.AddStep("UPDATE_BACKDROP", trinity.TriStepUpdate(uiRoot.GetRenderObject()))
            self.AddStep("RENDER_BACKDROP", trinity.TriStepRenderScene(uiRoot.GetRenderObject()))
        else:
            self.RemoveStep("UPDATE_BACKDROP")
            self.RemoveStep("RENDER_BACKDROP")

    def SetActiveCamera(self, camera, *args):
        """
        This call adds or removes the steps nessecary for controlling the camera
        depending on if 'camera' is None
        """
        if camera is None:
            self.RemoveStep("SET_VIEW")
            self.RemoveStep("SET_PROJECTION")
        else:
            self.AddStep("SET_VIEW", trinity.TriStepSetView(camera.viewMatrix))
            self.AddStep("SET_PROJECTION", trinity.TriStepSetProjection(camera.projectionMatrix))

    def EnableSceneUpdate(self, isEnabled):
        if isEnabled:
            self.AddStep("UPDATE_SCENE", trinity.TriStepUpdate(self.GetScene()))
        else:
            self.RemoveStep("UPDATE_SCENE")

    def SetStartOpacity(self, value):
        self.startOpacity = value

    def CreateRenderBlendEffect(self, msaaType):
        effect = trinity.Tr2Effect()
        if msaaType > 1:
            effect.effectFilePath = "res:/graphics/Effect/Managed/Space/PostProcess/OriginalFade.fx"
        else:
            effect.effectFilePath = "res:/graphics/Effect/Managed/Space/PostProcess/OriginalFade_noalpha.fx"
        param = trinity.Tr2FloatParameter()
        param.name = "Opacity"
        param.value = self.startOpacity
        effect.parameters.append(param)

        return effect
