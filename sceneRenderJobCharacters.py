import evegraphics.settings as gfxsettings

from .sceneRenderJobBase import SceneRenderJobBase
from .renderJobUtils import renderTargetManager as rtm
from . import _singletons
from . import _trinity as trinity

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
        "RENDER_TOOLS",
        "RENDER_UI",
    ]

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

        self.RemoveStep("SET_BACKBUFFER")
        self.RemoveStep("SET_DEPTH_STENCIL")
        self.RemoveStep("RESOLVE_IMAGE")

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

        if viewport:
            self.SetStepAttr("CLEAR", "isColorCleared", False)
        else:
            self.SetStepAttr("CLEAR", "isColorCleared", True)

        if viewport:
            msaaType = 1
        elif sm.IsServiceRunning("device"):
            aaQuality = gfxsettings.Get(gfxsettings.GFX_ANTI_ALIASING)
            msaaType = sm.GetService("device").GetMSAATypeFromQuality(aaQuality)
        else:
            msaaType = 4

        width, height = self.GetBackBufferSize()

        bbFormat = _singletons.device.GetRenderContext().GetBackBufferFormat()
        dsFormat = trinity.DEPTH_STENCIL_FORMAT.D24S8

        self.customBackBuffer = None
        self.customDepthStencil = rtm.GetDepthStencilAL(width, height, dsFormat, msaaType)
        self.AddStep("SET_DEPTH_STENCIL", trinity.TriStepPushDepthStencil(self.customDepthStencil))
        self.AddStep("RESTORE_DEPTH_STENCIL", trinity.TriStepPopDepthStencil())

        if msaaType <= 1:
            self.RemoveStep("SET_BACKBUFFER")
            self.RemoveStep("RESTORE_BACKBUFFER")
            self.RemoveStep("RESOLVE_IMAGE")
        else:
            self.customBackBuffer = rtm.GetRenderTargetMsaaAL(width, height, bbFormat, msaaType, 0)
            self.AddStep("SET_BACKBUFFER", trinity.TriStepPushRenderTarget(self.customBackBuffer))

            self.AddStep("RESTORE_BACKBUFFER", trinity.TriStepPopRenderTarget())

            self.AddStep("RESOLVE_IMAGE", trinity.TriStepResolve(self.GetBackBufferRenderTarget(), self.customBackBuffer))

    def UpdateViewport(self, viewport):
        if not self.customDepthStencil:
            return
        if viewport.width != self.customDepthStencil.width or viewport.height != self.customDepthStencil.height:
            self.SetSettingsBasedOnPerformancePreferences()

    def Enable(self, schedule=True):
        SceneRenderJobBase.Enable(self, schedule)
        self.EnableScatter(self.scatterEnabled)
        self.EnableSculpting(self.sculptingEnabled)

    def Disable(self):
        SceneRenderJobBase.Disable(self)
        self.EnableScatter(self.scatterEnabled)
        self.EnableSculpting(self.sculptingEnabled)

    def EnableScatter(self, isEnabled):
        import paperDoll
        self.scatterEnabled = isEnabled
        if self.enabled and isEnabled:
            self.AddStep("SCATTER", paperDoll.SkinLightmapRenderer.CreateScatterStep(self, self.GetScene(), False))
        else:
            self.RemoveStep("SCATTER")

    def EnableSculpting(self, isEnabled):
        import paperDoll
        self.sculptingEnabled = isEnabled
        if self.enabled and isEnabled:
            self.AddStep("RENDER_SCULPTING", paperDoll.AvatarGhost.CreateSculptingStep(self, False))
        else:
            self.RemoveStep("RENDER_SCULPTING")

    def SetCameraUpdate(self, job):
        self.AddStep("UPDATE_CAMERA", trinity.TriStepRunJob(job))

    def Set2DBackdropScene(self, backdrop):
        if backdrop is not None:
            self.AddStep("UPDATE_BACKDROP", trinity.TriStepUpdate(backdrop))
            self.AddStep("RENDER_BACKDROP", trinity.TriStepRenderScene(backdrop))
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
