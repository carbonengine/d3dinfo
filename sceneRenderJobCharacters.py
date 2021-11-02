import evegraphics.settings as gfxsettings

from .sceneRenderJobBase import SceneRenderJobBase
from .renderJobUtils import renderTargetManager as rtm
from . import _singletons
from . import _trinity as trinity
import trinity.evePostProcess
import charactercreator.client.grading as grading
import blue
import uthread
# paperDoll is imported later on, wth!



AA_SCALE_FACTOR = 2

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
        "PLACE_BG",
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
        "PUSH_RENDER_SCALE_RT",
        "PUSH_RENDER_SCALE_DS",
        "CLEAR_BB2",
        "SET_SCALE_VP",
        "RENDER_SCALE",
        "POP_RENDER_SCALE_RT",
        "POP_RENDER_SCALE_DS",
        "RESOLVE_FOR_POST",
        "PUSH_TRANS_RT",
        "PUSH_TRANS_DS",
        "CLEAR_TRANSOUTPUT",
        "RENDER_TRANSMISSION",
        "POP_TRANS_RT",
        "POP_TRANS_DS",
        "RESOLVE_IMAGE",

        "SET_COPY_TO_BB_STATE",
        "COPY_TO_BB",

        "SET_BLENDSOURCE",
        "PUSH_RENDER_BLEND_RT",
        "PUSH_RENDER_BLEND_DS",
        "SET_BLEND_VP",
        "RENDER_BLEND",
        "PLACE_AVATAR",
        "POP_RENDER_BLEND_RT",
        "POP_RENDER_BLEND_DS",
        "SET_PP_VIEWPORT",
        "RJ_POSTPROCESSING",
        "RENDER_TOOLS",
        "RENDER_UI",
    ]

    def setupPostProcess(self):
        resolveTarget = self.GetBackBufferRenderTarget()
        self.resolveTargetDimensions = (resolveTarget.width, resolveTarget.height)
        self.vp = trinity.TriViewport()
        self.pp_viewport = blue.BluePythonWeakRef(self.vp)
        self.derive_pp_viewport()

        if self.postProcess is None:
            self.AddStep("SET_PP_VIEWPORT", trinity.TriStepSetViewport(self.pp_viewport.object))
            self.postProcess = grading.PostProcess('res:/dx9/scene/postprocess/portraitLUT.red', resolveTarget, viewport=self.pp_viewport)
            self.AddStep("RJ_POSTPROCESSING", trinity.TriStepRunJob(self.postProcess.GetJob()))
        lut = grading.GetTexLUT(self)
        if lut is not None:
            lut.resourcePath = self.lut_res_path
        self.UpdatePostProcessingTexCoords(async=False)


    def derive_pp_viewport(self):
        self.pp_viewport.object.x = min(max(self.viewport.object.x, 0), self.resolveTargetDimensions[0])
        self.pp_viewport.object.y = min(max(self.viewport.object.y, 0), self.resolveTargetDimensions[1])
        if self.viewport.object.x + self.viewport.object.width < 0:
            self.pp_viewport.object.width = 0
        elif self.viewport.object.x < 0:
            self.pp_viewport.object.width = self.viewport.object.width + self.viewport.object.x
        elif self.viewport.object.x + self.viewport.object.width > self.resolveTargetDimensions[0]:
            self.pp_viewport.object.width = (self.resolveTargetDimensions[0] - self.viewport.object.x)
        else:
            self.pp_viewport.object.width = self.viewport.object.width
        if self.viewport.object.y + self.viewport.object.height < 0:
            self.pp_viewport.object.height = 0
        elif self.viewport.object.y < 0:
            self.pp_viewport.object.height = self.viewport.object.height + self.viewport.object.y
        elif self.viewport.object.y + self.viewport.object.height > self.resolveTargetDimensions[1]:
            self.pp_viewport.object.height = (self.resolveTargetDimensions[1] - self.viewport.object.y)
        else:
            self.pp_viewport.object.height = self.viewport.object.height

    def UpdatePostProcessingTexCoords_t(self):
        blue.synchro.Sleep(0)
        if self.postProcess is not None:
            step = None
            attempts = 0
            while step is None and attempts < 50:
                step = grading.GetLUTStepRenderEffect(self.postProcess.GetJob())
                if step is None:
                    blue.synchro.Sleep(0)

            if step is None:
                return

            self._UpdatePostProcessingTexCoords(step)


    def _UpdatePostProcessingTexCoords(self, step):
        texcoords = None
        if hasattr(self, "pp_viewport") and hasattr(self, 'resolveTargetDimensions') and hasattr(self, 'viewport') \
                and self.viewport is not None and self.viewport.object is not None and step is not None and \
                self.pp_viewport is not None and self.pp_viewport.object is not None:
            self.derive_pp_viewport()
            texcoords_top = float(self.pp_viewport.object.y) / self.resolveTargetDimensions[1]
            texcoords_left = float(self.pp_viewport.object.x) / self.resolveTargetDimensions[0]
            texcoords_bottom = float(self.pp_viewport.object.y + self.pp_viewport.object.height) / \
                               self.resolveTargetDimensions[1]
            texcoords_right = float(self.pp_viewport.object.x + self.pp_viewport.object.width) / \
                              self.resolveTargetDimensions[0]
            texcoords = (texcoords_left, texcoords_top, texcoords_right, texcoords_bottom)
        if texcoords is not None:
            step.tlTexCoord = (texcoords[0], texcoords[1])
            step.brTexCoord = (texcoords[2], texcoords[3])

            self.postProcess.UpdateViewport(self.pp_viewport.object)

        self.enabled = True


    def UpdatePostProcessingTexCoords(self, async=False):
        if async:
            uthread.new(self.UpdatePostProcessingTexCoords_t)
        else:
            if self.postProcess is not None:
                step = grading.GetLUTStepRenderEffect(self.postProcess.GetJob())
                self._UpdatePostProcessingTexCoords(step)


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
        self.postBackBuffer = None
        self.postProcess = None
        self.startOpacity = 1.0
        self.dx9_active = trinity.platform == "dx9"
        self.releasing = False
        self.rebuilding = False
        self.rs_effect = None
        self.msaaType = 1
        self.supersampling = False
        self.aaQuality = gfxsettings.AA_QUALITY_MSAA_MEDIUM

        # There is a bug in Intel drivers for macOS 10.x (at least, possibly 11 as well) that prevents rendering into
        # a render target after it was a destination of MSAA resolve. As a workaround we resolve into a temp render
        # target and then blit it to the back buffer
        self._needsIntelWorkaround = False
        self._DetectIntelOnMacOS()

    def _DetectIntelOnMacOS(self):
        self._needsIntelWorkaround = False
        if trinity.platform == "metal":
            try:
                info = trinity.adapters.GetAdapterInfo(trinity.mainWindow.GetWindowState().adapter)
                self._needsIntelWorkaround = info.vendorID == 32902
            except:
                pass

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
        self.postBackBuffer = None


    def DoPrepareResources(self):
        """
        This function is called when the device is restored. 
        This function may raise exceptions attempting to create resources!
        """
        self._DetectIntelOnMacOS()
        self.SetSettingsBasedOnPerformancePreferences()

    def GetMSAAType(self):
        if self.dx9_active:
            msaaType = 1
            aaQuality = gfxsettings.AA_QUALITY_DISABLED
        elif sm.IsServiceRunning("device"):
            aaQuality = gfxsettings.Get(gfxsettings.GFX_ANTI_ALIASING)
            msaaType = sm.GetService("device").GetMSAATypeFromQuality(aaQuality)
        else:
            msaaType = 4
            aaQuality = gfxsettings.AA_QUALITY_MSAA_MEDIUM

        return msaaType, aaQuality

    def SetSettingsBasedOnPerformancePreferences(self):
        if not self.enabled:
            return
        viewport = self.GetViewport()
        self.SetStepAttr("CLEAR", "isColorCleared", True)
        msaaType, aaQuality = self.GetMSAAType()

        self.msaaType = msaaType
        self.aaQuality = aaQuality
        self.supersampling = False
        if self.aaQuality == gfxsettings.AA_QUALITY_TAA_HIGH and viewport:
            self.supersampling = True

        if msaaType <= 1:
            self.SetStepAttr("CLEAR", "isColorCleared", False)

        if not self.dx9_active:
            width, height = self.SetupBufferedViewports(viewport)
            self.SetupPasses(viewport, msaaType, width, height)
        else:
            width, height = self.GetBackBufferSize()
            self.SetupDX9Passes(viewport, width, height, msaaType)

        self.UpdatePostProcessingTexCoords(async=True)


    def CropVPObj(self, viewport_obj, target_vp_obj):
        target_vp_obj.x = viewport_obj.x
        target_vp_obj.y = viewport_obj.y
        target_vp_obj.width = viewport_obj.width
        target_vp_obj.height = viewport_obj.height

        if viewport_obj.x < 0:
            target_vp_obj.x = 0
            target_vp_obj.width = viewport_obj.width + viewport_obj.x

        if viewport_obj.y < 0:
            target_vp_obj.y = 0
            target_vp_obj.height = viewport_obj.height + viewport_obj.y

    def CropLocalVPObj(self, viewport_obj, target_vp_obj):
        target_vp_obj.x = viewport_obj.x
        target_vp_obj.y = viewport_obj.y
        target_vp_obj.width = viewport_obj.width
        target_vp_obj.height = viewport_obj.height

        if self.cropped_scr_vp_obj.x == 0:
            target_vp_obj.width = self.cropped_scr_vp_obj.width
            target_vp_obj.x = viewport_obj.width - target_vp_obj.width

        if self.cropped_scr_vp_obj.y == 0:
            target_vp_obj.height = self.cropped_scr_vp_obj.height
            target_vp_obj.y = viewport_obj.height - target_vp_obj.height

    def SetupPasses(self, viewport, msaaType, width, height):
        self.enabled = False
        bbFormat = _singletons.device.GetRenderContext().GetBackBufferFormat()
        dsFormat = trinity.DEPTH_STENCIL_FORMAT.D24S8

        self.customBackBuffer = None
        self.resolveBuffer = None
        if self.supersampling:
            self.customDepthStencil = rtm.GetDepthStencilAL(width * AA_SCALE_FACTOR, height * AA_SCALE_FACTOR, dsFormat, 1)
        else:
            self.customDepthStencil = rtm.GetDepthStencilAL(width, height, dsFormat, msaaType)
        self.AddStep("SET_DEPTH_STENCIL", trinity.TriStepPushDepthStencil(self.customDepthStencil))
        self.AddStep("RESTORE_DEPTH_STENCIL", trinity.TriStepPopDepthStencil())

        self.RemoveStep("SET_COPY_TO_BB_STATE")
        self.RemoveStep("COPY_TO_BB")

        if viewport:
            self.bgBuffer = rtm.GetRenderTargetAL(width, height, 1, bbFormat, index=2)
            self.blendsource = rtm.GetRenderTargetAL(width, height, 1, bbFormat, index=1)
            if self.dx9_active:
                self.customBackBuffer = rtm.GetRenderTargetAL(width, height, 1, bbFormat, index=3)
            else:
                self.transOutput = rtm.GetRenderTargetAL(width, height, 1, bbFormat, index=5)
                if self.supersampling:
                    # NOTE that for AA_QUALITY_TAA_HIGH we are forcing MSAA to 1 with this even though the variable says 4!
                    self.customBackBuffer = rtm.GetRenderTargetAL(width * AA_SCALE_FACTOR, height * AA_SCALE_FACTOR, 1, bbFormat, index=3)
                    self.customBackBuffer2 = rtm.GetRenderTargetAL(width, height, 1, bbFormat, index=4)
                else:
                    self.customBackBuffer = rtm.GetRenderTargetMsaaAL(width, height, bbFormat, msaaType, 0, index=3)
                    self.postBackBuffer = rtm.GetRenderTargetAL(width, height, 1, bbFormat, index=6)
            self.AddStep("SET_BACKBUFFER", trinity.TriStepPushRenderTarget(self.customBackBuffer))
            self.AddStep("SET_BG_LAYER", trinity.TriStepCopyRenderTarget(self.bgBuffer, self.GetBackBufferRenderTarget(), self.cropped_local_vp_obj, self.cropped_scr_vp_obj))
            if msaaType <= 1:
                self.AddStep("PLACE_BG", trinity.TriStepCopyRenderTarget(self.customBackBuffer, self.GetBackBufferRenderTarget(), self.cropped_local_vp_obj, self.cropped_scr_vp_obj))
            self.AddStep("RESOLVE_IMAGE", trinity.TriStepResolve(self.blendsource, self.transOutput))
            if self.supersampling:
                self.AddStep("PUSH_RENDER_SCALE_RT", trinity.TriStepPushRenderTarget(self.customBackBuffer2))
                self.AddStep("PUSH_RENDER_SCALE_DS", trinity.TriStepPushDepthStencil(None))
                self.AddStep("CLEAR_BB2", trinity.TriStepClear((0.0, 0.0, 0.0, 0.0)))
                self.SetStepAttr("CLEAR_BB2", "isColorCleared", True)
                self.AddStep("SET_SCALE_VP", trinity.TriStepSetViewport(self.local_scale_vp_obj))
                self.rs_effect = self.CreateRenderScaleEffect(self.customBackBuffer)
                self.AddStep("RENDER_SCALE", trinity.TriStepRenderEffect(self.rs_effect))
                self.AddStep("POP_RENDER_SCALE_RT", trinity.TriStepPopRenderTarget())
                self.AddStep("POP_RENDER_SCALE_DS", trinity.TriStepPopDepthStencil())
            else:
                self.RemoveStep("PUSH_RENDER_SCALE_RT")
                self.RemoveStep("PUSH_RENDER_SCALE_DS")
                self.RemoveStep("CLEAR_BB2")
                self.RemoveStep("SET_SCALE_VP")
                self.RemoveStep("RENDER_SCALE")
                self.RemoveStep("POP_RENDER_SCALE_RT")
                self.RemoveStep("POP_RENDER_SCALE_DS")
            self.AddStep("PUSH_RENDER_BLEND_RT", trinity.TriStepPushRenderTarget(self.GetBackBufferRenderTarget()))
            self.AddStep("PUSH_RENDER_BLEND_DS", trinity.TriStepPushDepthStencil(None))
            self.AddStep("SET_BLEND_VP", trinity.TriStepSetViewport(self.scr_vp_obj))
            self.AddStep("RENDER_BLEND", trinity.TriStepRenderEffect(self.CreateRenderBlendEffect(msaaType, self.bgBuffer, self.blendsource)))
            self.AddStep("PLACE_AVATAR", trinity.TriStepCopyRenderTarget(self.bgBuffer, self.GetBackBufferRenderTarget(), self.scr_vp_obj, self.local_vp_obj))
            self.AddStep("POP_RENDER_BLEND_RT", trinity.TriStepPopRenderTarget())
            self.AddStep("POP_RENDER_BLEND_DS", trinity.TriStepPopDepthStencil())
            self.setupPostProcess()
            self.AddStep("CLEAR_TRANSOUTPUT", trinity.TriStepClear((0.0, 0.0, 0.0, 0.0)))
            self.SetStepAttr("CLEAR_TRANSOUTPUT", "isColorCleared", True)
            self.AddStep("PUSH_TRANS_RT", trinity.TriStepPushRenderTarget(self.transOutput))
            self.AddStep("PUSH_TRANS_DS", trinity.TriStepPushDepthStencil(None))
            if self.supersampling:
                self.AddStep("RENDER_TRANSMISSION", trinity.TriStepRenderEffect(self.CreateTransmissionEffect(self.customBackBuffer2)))
                self.RemoveStep("RESOLVE_FOR_POST")
            else:
                self.AddStep("RESOLVE_FOR_POST", trinity.TriStepResolve(self.postBackBuffer, self.customBackBuffer))
                self.AddStep("RENDER_TRANSMISSION", trinity.TriStepRenderEffect(self.CreateTransmissionEffect(self.postBackBuffer)))
            self.AddStep("POP_TRANS_RT", trinity.TriStepPopRenderTarget())
            self.AddStep("POP_TRANS_DS", trinity.TriStepPopDepthStencil())
            self.AddStep("RESTORE_BACKBUFFER", trinity.TriStepPopRenderTarget())
        else:
            if msaaType <= 1:
                self.RemoveStep("SET_BACKBUFFER")
                self.RemoveStep("RESTORE_BACKBUFFER")
                self.RemoveStep("RESOLVE_IMAGE")
            else:
                self.customBackBuffer = rtm.GetRenderTargetMsaaAL(width, height, bbFormat, msaaType, 0)
                self.AddStep("SET_BACKBUFFER", trinity.TriStepPushRenderTarget(self.customBackBuffer))
                self.AddStep("RESTORE_BACKBUFFER", trinity.TriStepPopRenderTarget())

                if self._needsIntelWorkaround:
                    self.resolveBuffer = rtm.GetRenderTargetAL(width, height, 1, bbFormat, 6)
                    self.AddStep("RESOLVE_IMAGE", trinity.TriStepResolve(self.resolveBuffer, self.customBackBuffer))

                    self.AddStep("SET_COPY_TO_BB_STATE", trinity.TriStepSetStdRndStates(trinity.RM_FULLSCREEN))
                    self.AddStep("COPY_TO_BB", trinity.TriStepRenderTexture(self.resolveBuffer))
                else:
                    self.AddStep("RESOLVE_IMAGE", trinity.TriStepResolve(self.GetBackBufferRenderTarget(), self.customBackBuffer))

            self.enabled = True

    def SetupDX9Passes(self, viewport, width, height, msaaType):

        self.enabled = False

        bbFormat = _singletons.device.GetRenderContext().GetBackBufferFormat()
        dsFormat = trinity.DEPTH_STENCIL_FORMAT.D24S8

        self.customBackBuffer = None
        self.customDepthStencil = rtm.GetDepthStencilAL(width, height, dsFormat, msaaType)
        self.AddStep("SET_DEPTH_STENCIL", trinity.TriStepPushDepthStencil(self.customDepthStencil))
        self.AddStep("RESTORE_DEPTH_STENCIL", trinity.TriStepPopDepthStencil())

        if viewport:
            self.bgBuffer = rtm.GetRenderTargetAL(width, height, 1, bbFormat)
            self.blendsource = rtm.GetRenderTargetAL(width, height, 1, bbFormat, index=1)
            self.AddStep("SET_BG_LAYER", trinity.TriStepResolve(self.bgBuffer, self.GetBackBufferRenderTarget()))
            self.AddStep("SET_BLENDSOURCE", trinity.TriStepResolve(self.blendsource, self.GetBackBufferRenderTarget()))
            self.AddStep("PUSH_RENDER_BLEND_RT", trinity.TriStepPushRenderTarget(self.GetBackBufferRenderTarget()))
            self.AddStep("PUSH_RENDER_BLEND_DS", trinity.TriStepPushDepthStencil(None))
            self.AddStep("RENDER_BLEND", trinity.TriStepRenderEffect(self.CreateRenderBlendEffect(msaaType, self.bgBuffer, self.blendsource)))
            self.AddStep("POP_RENDER_BLEND_RT", trinity.TriStepPopRenderTarget())
            self.AddStep("POP_RENDER_BLEND_DS", trinity.TriStepPopDepthStencil())
            self.setupPostProcess()

        self.RemoveStep("SET_BACKBUFFER")
        self.RemoveStep("RESTORE_BACKBUFFER")
        self.RemoveStep("RESOLVE_IMAGE")
        self.enabled = True

    def SetupBufferedViewports(self, viewport):
        if not viewport:
            width, height = self.GetBackBufferSize()
        else:
            self.scr_vp_obj = trinity.TriViewport()
            self.scr_vp = blue.BluePythonWeakRef(self.scr_vp_obj)
            self.scr_vp.object.x = viewport.x
            self.scr_vp.object.y = viewport.y
            self.scr_vp.object.width = viewport.width
            self.scr_vp.object.height = viewport.height
            self.scr_vp.object.minZ = viewport.minZ
            self.scr_vp.object.maxZ = viewport.maxZ
            self.cropped_scr_vp_obj = trinity.TriViewport()
            self.CropVPObj(self.scr_vp_obj, self.cropped_scr_vp_obj)
            self.local_vp_obj = trinity.TriViewport()
            self.local_vp = blue.BluePythonWeakRef(self.local_vp_obj)
            self.local_vp.object.x = 0
            self.local_vp.object.y = 0
            if self.supersampling:
                self.local_vp.object.width = viewport.width * AA_SCALE_FACTOR
                self.local_vp.object.height = viewport.height * AA_SCALE_FACTOR
            else:
                self.local_vp.object.width = viewport.width
                self.local_vp.object.height = viewport.height
            self.local_vp.object.minZ = viewport.minZ
            self.local_vp.object.maxZ = viewport.maxZ
            self.local_scale_vp_obj = trinity.TriViewport()
            self.local_scale_vp = blue.BluePythonWeakRef(self.local_scale_vp_obj)
            self.local_scale_vp.object.x = 0
            self.local_scale_vp.object.y = 0
            self.local_scale_vp.object.width = viewport.width
            self.local_scale_vp.object.height = viewport.height
            self.local_scale_vp.object.minZ = viewport.minZ
            self.local_scale_vp.object.maxZ = viewport.maxZ
            self.cropped_local_vp_obj = trinity.TriViewport()
            self.CropLocalVPObj(self.local_scale_vp_obj, self.cropped_local_vp_obj)
            width, height = viewport.width, viewport.height
            if not self.dx9_active:
                self._SetViewport(self.local_vp_obj)
            else:
                self._SetViewport(self.scr_vp_obj)

        return width, height

    def UpdateSteps(self):
        if not self.dx9_active:
            self.RemoveStep("SET_BG_LAYER")
            self.RemoveStep("PLACE_BG")
            self.AddStep("SET_BG_LAYER", trinity.TriStepCopyRenderTarget(self.bgBuffer, self.GetBackBufferRenderTarget(), self.cropped_local_vp_obj, self.cropped_scr_vp_obj))
            if self.msaaType <= 1:
                self.AddStep("PLACE_BG", trinity.TriStepCopyRenderTarget(self.customBackBuffer, self.GetBackBufferRenderTarget(), self.cropped_local_vp_obj, self.cropped_scr_vp_obj))
            self.RemoveStep("PLACE_AVATAR")
            self.AddStep("PLACE_AVATAR", trinity.TriStepCopyRenderTarget(self.bgBuffer, self.GetBackBufferRenderTarget(), self.scr_vp_obj, self.local_vp_obj))
            self.RemoveStep("SET_BLEND_VP")
            self.AddStep("SET_BLEND_VP", trinity.TriStepSetViewport(self.scr_vp_obj))
            self.RemoveStep("SET_PP_VIEWPORT")
            self.AddStep("SET_PP_VIEWPORT", trinity.TriStepSetViewport(self.pp_viewport.object))

    def UpdateViewport(self, new_viewport):
        print("sceneRenderJobCharacters: Updating viewport %s" % str((new_viewport.x, new_viewport.y, new_viewport.height, new_viewport.width)))
        if not hasattr(self, 'scr_vp_obj') or not hasattr(self, 'local_vp_obj') or self.scr_vp_obj is None or self.local_vp_obj is None:
            return
        viewport = self.scr_vp_obj
        self.CropVPObj(self.scr_vp_obj, self.cropped_scr_vp_obj)
        self.CropLocalVPObj(self.local_vp_obj, self.cropped_local_vp_obj)
        msaaType, aaQuality = self.GetMSAAType()
        if viewport is None or new_viewport.width != viewport.width or new_viewport.height != viewport.height or self.msaaType != msaaType or self.aaQuality != aaQuality or self.customDepthStencil is None:
            self.SetViewport(new_viewport)
            self.SetSettingsBasedOnPerformancePreferences()
        else:
            self.SetViewport(new_viewport)
            self.UpdateSteps()
            self.UpdatePostProcessingTexCoords()


    def SetViewport(self, viewport):
        """
        Sets the main viewport.
        """
        if viewport is None:
            self.RemoveStep("SET_VIEWPORT")
            self.viewport = None
        else:
            self.viewport = blue.BluePythonWeakRef(viewport)
            self.SetupBufferedViewports(viewport)

    def _SetViewport(self, viewport):
        self.AddStep("SET_VIEWPORT", trinity.TriStepSetViewport(viewport))

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

    def CreateRenderBlendEffect(self, msaaType, blitOriginalRT, blitCurrentRT):
        effect = trinity.Tr2Effect()
        effect.StartUpdate()
        if msaaType > 1:
            effect.effectFilePath = "res:/graphics/Effect/Managed/Space/PostProcess/OriginalFade.fx"
        else:
            effect.effectFilePath = "res:/graphics/Effect/Managed/Space/PostProcess/OriginalFade_noalpha.fx"
        param = trinity.Tr2FloatParameter()
        param.name = "Opacity"
        param.value = self.startOpacity
        effect.parameters.append(param)
        self.blitOriginalRes = trinity.TriTextureParameter()
        self.blitOriginalRes.name = "BlitOriginal"
        self.blitOriginalRes.SetResource(trinity.TriTextureRes(blitOriginalRT))
        effect.resources.append(self.blitOriginalRes)
        self.blitCurrentRes = trinity.TriTextureParameter()
        self.blitCurrentRes.name = "BlitCurrent"
        self.blitCurrentRes.SetResource(trinity.TriTextureRes(blitCurrentRT))
        effect.resources.append(self.blitCurrentRes)
        effect.EndUpdate()
        return effect


    def CreateRenderScaleEffect(self, rt_buffer):
        effect = trinity.Tr2Effect()
        effect.StartUpdate()
        effect.effectFilePath = "res:/graphics/Effect/Managed/Space/PostProcess/ScaleRT.fx"
        param = trinity.Tr2Vector2Parameter()
        param.name = "OutSize"
        param.value = (self.scr_vp_obj.width, self.scr_vp_obj.height)
        effect.parameters.append(param)


        self.scaleSourceRes = trinity.TriTextureParameter()
        self.scaleSourceRes.name = "ScaleSource"
        self.scaleSourceRes.SetResource(trinity.TriTextureRes(rt_buffer))
        effect.resources.append(self.scaleSourceRes)
        effect.EndUpdate()
        return effect

    def RebuildPostprocess(self):
        self.postProcess = None
        self.RemoveStep("SET_PP_VIEWPORT")
        self.RemoveStep("RJ_POSTPROCESSING")
        self.setupPostProcess()

    def CreateTransmissionEffect(self, rt_buffer):
        effect = trinity.Tr2Effect()
        effect.StartUpdate()
        effect.effectFilePath = "res:/graphics/Effect/Managed/Space/PostProcess/DigiScramble.fx"
        param = trinity.Tr2FloatParameter()
        param.name = "Amount"
        param.value = 0.0
        effect.parameters.append(param)


        self.scrambleSourceRes = trinity.TriTextureParameter()
        self.scrambleSourceRes.name = "ScrambleSource"
        self.scrambleSourceRes.SetResource(trinity.TriTextureRes(rt_buffer))
        effect.resources.append(self.scrambleSourceRes)
        effect.EndUpdate()

        self.scrambleCurveSet = trinity.TriCurveSet()
        self.scrambleCurveSet.name = "ScrambleCurveSet"
        self.scrambleCurveSet.playOnLoad = False

        scrambleExpression = trinity.Tr2CurveScalarExpression()
        scrambleExpression.name = "ScrambleExpression"
        scrambleExpression.expression = "(clamp(2 - time, 0, 0.7) + 0.3) * randhash(0.5, 1, time)"

        scrambleExpressionBinding = trinity.TriValueBinding()
        scrambleExpressionBinding.name = "ScrambleExpressionBinding"
        scrambleExpressionBinding.sourceAttribute = "currentValue"
        scrambleExpressionBinding.destinationAttribute = "value"
        scrambleExpressionBinding.sourceObject = scrambleExpression
        scrambleExpressionBinding.destinationObject = param

        self.scrambleCurveSet.bindings.append(scrambleExpressionBinding)
        self.scrambleCurveSet.curves.append(scrambleExpression)

        return effect

    def PlaceTransmissionEffectInScene(self, scene):
        scrambleCurveSet = None
        for curveSet in scene.curveSets:
            if curveSet.name == "ScrambleCurveSet":
                scrambleCurveSet = curveSet

        if scrambleCurveSet is None and hasattr(self, 'scrambleCurveSet') and self.scrambleCurveSet is not None:
            scene.curveSets.append(self.scrambleCurveSet)