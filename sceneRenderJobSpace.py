import logging
import blue
import evegraphics.settings as gfxsettings

from . import _trinity as trinity
from . import _singletons
from .renderJob import CreateRenderJob
from .sceneRenderJobBase import SceneRenderJobBase
from .renderJobUtils import renderTargetManager as rtm
from . import evePostProcess

logger = logging.getLogger(__name__)


def CreateSceneRenderJobSpace(name = None, stageKey = None):
    """
    We can't use __init__ on a decorated class, so we provide a creation function that does it for us
    """
    newRJ = SceneRenderJobSpace()
    if name is not None:
        newRJ.ManualInit(name)
    else:
        newRJ.ManualInit()

    newRJ.SetMultiViewStage(stageKey)
    return newRJ
        

class SceneRenderJobSpace(SceneRenderJobBase):
    """
    This is a renderjob manager for creating and managing the renderjob to forwards 
    render the eve space scene.
    """

    # This is a master list that we can refer to, when we want to insert steps that are not already in
    # the render steps, by looking for the prior or next step that exists, in order to position the new one
    # See: AddStep
    renderStepOrder = [
        "PRESENT_SWAPCHAIN",
        "SET_SWAPCHAIN_RT",
        "SET_SWAPCHAIN_DEPTH",
        "UPDATE_PHYSICS",
        "UPDATE_SCENE",
        "SET_CUSTOM_RT",
        "SET_DEPTH",
        "SET_VAR_DEPTH",
        "SET_VAR_DEPTH_MSAA",
        "SET_VIEWPORT",
        "CAMERA_UPDATE",
        "SET_PROJECTION",
        "SET_VIEW",
        "CLEAR",
        "BEGIN_RENDER",
        "RENDER_BACKGROUND",
        "RENDER_DEPTH_PASS",
        "RENDER_MAIN_PASS",
        "DO_DISTORTIONS",
        "END_RENDERING",
        "RENDER_DEBUG",
        "UPDATE_TOOLS", 
        "RENDER_PROXY", 
        "RENDER_INFO",
        "RENDER_VISUAL",
        "RENDER_TOOLS",   
        "SET_FINAL_RT",
        "RESTORE_DEPTH",
        "SET_PERFRAME_DATA",
        "RJ_POSTPROCESSING",
        "FINAL_BLIT",
        "SET_VAR_GATHER",
        "FXAA_CLEAR",
        "FXAA",
        "FPS_COUNTER"
    ]

    # This is a template for creating quad and multi-view renderjobs
    # it breaks things down into passes, with shared steps in between
    multiViewStages = []

    visualizations = []
    
    renderTargetList = []
    
    def _ManualInit(self, name = "SceneRenderJobSpace"):
        """
        Decorated classes cannot use a normal init function, so this must be called manually
        This version is called from ManualInit on SceneRenderJobBase
        """
        # Active scenes
        self.scene = None
        self.clientToolsScene = None
        
        # The active eve space scene key(default, map etc.)
        self.activeSceneKey = None
        
        # The active camera, this ref might be unneccessary, keep in mind failure to reset
        self.camera = None
        
        # All the surfaces needed for different settings
        self.customBackBuffer = None
        self.customDepthStencil = None
        self.depthTexture = None
        self.blitTexture = None
        self.distortionTexture = None

        # The shadow map
        self.shadowMap = None
        
        # A ref to the ui
        self.ui = None
        
        # Settings variables, do we really need to store these? don't think so tbh
        self.hdrEnabled = False
        self.usePostProcessing = False
        self.shadowQuality = 0
        self.useDepth = False

        self.antiAliasingEnabled = False
        self.antiAliasingQuality = 0
        self.aaQuality = 0
        self.useFXAA = False
        self.fxaaEnabled = False
        self.fxaaQuality = "FXAA_High"
        self.msaaEnabled = False
        self.doDepthPass = False
        self.forceDepthPass = False
        self.msaaType = 4

        self.distortionEffectsEnabled = False
        
        self.fxaaEffect = None
        
        self.bbFormat = _singletons.device.GetRenderContext().GetBackBufferFormat()

        self.prepared = False

        self.postProcessingJob = evePostProcess.EvePostProcessingJob()
        self.distortionJob = evePostProcess.EvePostProcessingJob()
        self.backgroundDistortionJob = evePostProcess.EvePostProcessingJob()

        self.sceneDesaturation = SceneDesaturation(self.postProcessingJob)

        self.overrideSettings = {}

        self.SetSettingsBasedOnPerformancePreferences()

        self.updateJob = CreateRenderJob(name + "_Update")
        self.updateJob.scheduled = False
        

    def Enable(self, schedule=True):
        SceneRenderJobBase.Enable(self, schedule)
        self.SetSettingsBasedOnPerformancePreferences()


    def SuspendRendering(self):
        SceneRenderJobBase.UnscheduleRecurring(self)
        self.scheduled = False


    def Start(self):
        SceneRenderJobBase.Start(self)
        if self.updateJob is not None and not self.updateJob.scheduled:
            self.updateJob.ScheduleUpdate()
            self.updateJob.scheduled = True


    def Disable(self):
        SceneRenderJobBase.Disable(self)
        if self.updateJob is not None and self.updateJob.scheduled:
            self.updateJob.UnscheduleUpdate()
            self.updateJob.scheduled = False


    def UnscheduleRecurring(self, scheduledRecurring=None):
        SceneRenderJobBase.UnscheduleRecurring(self, scheduledRecurring)
        if self.updateJob is not None and self.updateJob.scheduled:
            self.updateJob.UnscheduleUpdate()
            self.updateJob.scheduled = False

  
    def SetClientToolsScene(self, scene):
        """
        A function that sets a primitive scene for rendering client tools (for the
        Dungeon Editor).
        """
        if scene is None:
            self.clientToolsScene = None
        else:
            self.clientToolsScene = blue.BluePythonWeakRef(scene)

        self.AddStep("UPDATE_TOOLS", trinity.TriStepUpdate(scene))
        self.AddStep("RENDER_TOOLS", trinity.TriStepRenderScene(scene))


    def GetClientToolsScene(self):
        """
        A function that gets the client tools scene (for the Dungeon Editor)
        """
        if self.clientToolsScene is None:
            return None
        else:
            return self.clientToolsScene.object
        

    def SetActiveCamera(self, camera=None, view=None, projection=None):
        """
        This call adds or removes the steps nessecary for controlling the camera
        depending on if 'camera' is None
        """
        if camera is None and view is None and projection is None:
            self.RemoveStep("SET_VIEW")
            self.RemoveStep("SET_PROJECTION")
            return

        if camera is not None:
            self.AddStep("SET_VIEW", trinity.TriStepSetView(None, camera))
            self.AddStep("SET_PROJECTION", trinity.TriStepSetProjection(camera.projectionMatrix))
        if view is not None:
            self.AddStep("SET_VIEW", trinity.TriStepSetView(view))
        if projection is not None:
            self.AddStep("SET_PROJECTION", trinity.TriStepSetProjection(projection))
    

    def SetActiveScene(self, scene, key=None):
        """
        This function sets the scene and the scene key associated with it
        """

        self.activeSceneKey = key
        self.SetScene(scene)

        self.postProcessingJob.SetActiveKey(key)


    def _SetDepthMap(self):
        """
        Set depth map to the scene
        """
        if not self.enabled:
            return
        if self.GetScene() is None:
            return
            
        if hasattr(self.GetScene(), "depthTexture"):
            if self.doDepthPass:
                self.GetScene().depthTexture = self.depthTexture
            else:
                self.GetScene().depthTexture = None


    def _SetDistortionMap(self):
        """
        Set depth map to the scene
        """
        if not self.enabled:
            return
        if self.GetScene() is None:
            return
            
        if hasattr(self.GetScene(), "distortionTexture"):
            self.GetScene().distortionTexture = self.distortionTexture


    def _SetShadowMap(self):
        """
        Set shadow map to the scene
        """
        scene = self.GetScene()
        if scene is None:
            return
            
        # set it to scene or null it 
        if self.shadowQuality > 1:
            scene.shadowMap = self.shadowMap
            scene.shadowFadeThreshold = 180
            scene.shadowThreshold = 80
        elif self.shadowQuality > 0:
            scene.shadowMap = self.shadowMap
            scene.shadowFadeThreshold = 200
            scene.shadowThreshold = 120
        else:
            scene.shadowMap = None


    def ForceDepthPass(self, enabled):
        """ Force a special depth pass under SM_3_0_DEPTH """
        self.forceDepthPass = enabled


    def EnablePostProcessing(self, enabled):
        """
        Indicate weather post processing is allowed or not
        """
        if enabled:
            self.AddStep("RJ_POSTPROCESSING", trinity.TriStepRunJob(self.postProcessingJob))
        else:
            self.RemoveStep("RJ_POSTPROCESSING")


    def _RefreshPostProcessingJob(self, job, enabled):
        if enabled:
            job.Prepare(self._GetSourceRTForPostProcessing(), self.blitTexture, destination=self._GetDestinationRTForPostProcessing())
            job.CreateSteps()
        else:
            job.Release()


    def _GetSourceRTForPostProcessing(self):
        if self.customBackBuffer is not None:
            return self.customBackBuffer
        return self.GetBackBufferRenderTarget()


    def _GetDestinationRTForPostProcessing(self):
        if self.useFXAA and self.antiAliasingEnabled:
            return self.customBackBuffer
        return None


    def _DoFormatConversionStep(self, hdrTexture, msaaTexture=None):
        """
        If we have no post processing, but we do have HDR and/or MSAA, we need to take
        a HDR texture into an LDR backbuffer, and/or an MSAA texture into a non-MSAA backbuffer.
        Make the old StretchBlt/CopyTextureToRt magic explicit by doing this manually:
        - if we have MSAA and HDR, resolve MSAA -> HDR, then full-screen-blit HDR -> LDR
        - if we have MSAA but no HDR, we shouldn't get here, MSAA should have exactly the same
             format as the backbuffer, and it can just be Resolve()d.
        - if we have just HDR, full-screen-blit HDR -> LDR
        """
        job = CreateRenderJob()
        job.name = 'DoFormatConversion'
        if msaaTexture is not None:
            if hdrTexture is not None:
                job.steps.append(trinity.TriStepResolve(hdrTexture, msaaTexture))
            else:
                job.steps.append(trinity.TriStepResolve(self.GetBackBufferRenderTarget(), msaaTexture))
                return trinity.TriStepRunJob(job)

        job.steps.append(trinity.TriStepSetStdRndStates(trinity.RM_FULLSCREEN))
        job.steps.append(trinity.TriStepRenderTexture(hdrTexture))
        return trinity.TriStepRunJob(job)


    def _GetRTForDepthPass(self):
        return self.GetBackBufferRenderTarget()


    def _CreateDepthPass(self):
        rj = trinity.TriRenderJob()

        if _singletons.platform != 'dx11' and self.enabled and self.doDepthPass and self.depthTexture is not None:
            rj.steps.append(trinity.TriStepPushViewport())
            rj.steps.append(trinity.TriStepPushRenderTarget(self._GetRTForDepthPass()))
            rj.steps.append(trinity.TriStepPushDepthStencil(self.depthTexture))
            # This amazing viewport foo is currently the cleanest way to guarantee correct viewports
            # in the client, embedded jobs, maya and tp2.
            rj.steps.append(trinity.TriStepPopViewport())
            rj.steps.append(trinity.TriStepPushViewport())
            rj.steps.append(trinity.TriStepRenderPass(self.GetScene(), trinity.TRIPASS_DEPTH_PASS))
            rj.steps.append(trinity.TriStepPopDepthStencil())
            rj.steps.append(trinity.TriStepPopRenderTarget())
            rj.steps.append(trinity.TriStepPopViewport())

        self.AddStep("RENDER_DEPTH_PASS", trinity.TriStepRunJob(rj))


    def _CreateBackgroundStep(self, scene=None):
        if scene is None:
            scene = self.GetScene()

        job = CreateRenderJob()
        job.steps.append(trinity.TriStepRenderPass(scene, trinity.TRIPASS_BACKGROUND_RENDER))
        job.steps.append(trinity.TriStepRunJob(self.backgroundDistortionJob))

        self.AddStep("RENDER_BACKGROUND", trinity.TriStepRunJob(job))


    def _SetBackgroundScene(self, scene):
        backgroundJob = self.GetStep("RENDER_BACKGROUND")
        if backgroundJob is not None:
            backgroundJob.job.steps[0].scene = scene


    def _SetScene(self, scene):
        """
        Sets a scene into the render job
        """
        self.currentMultiViewStageKey
        if self.updateJob is not None:
            if len(self.updateJob.steps) > 0:
                self.updateJob.steps[0].object = scene
        else:
            self.SetStepAttr("UPDATE_SCENE", 'object', scene)
        self.SetStepAttr("RENDER_MAIN_PASS", 'scene', scene) 
        self.SetStepAttr("BEGIN_RENDER", 'scene', scene)
        self.SetStepAttr("END_RENDERING", 'scene', scene)
        self.SetStepAttr("RENDER_MAIN_PASS", 'scene', scene)
        self.SetStepAttr("SET_PERFRAME_DATA", 'scene', scene)
        self._CreateDepthPass()
        self._SetBackgroundScene(scene)

        self.ApplyPerformancePreferencesToScene()


    def _CreateBasicRenderSteps(self):
        # Scene update and render
        if self.updateJob is not None:
            if len(self.updateJob.steps) == 0:
                self.updateJob.steps.append(trinity.TriStepUpdate(self.GetScene()))
                self.updateJob.steps[0].name = "UPDATE_SCENE"
            else:
                self.updateJob.steps[0] = trinity.TriStepUpdate(self.GetScene())
        else:
            self.AddStep("UPDATE_SCENE", trinity.TriStepUpdate(self.GetScene()))
        self.AddStep("BEGIN_RENDER", trinity.TriStepRenderPass(self.GetScene(), trinity.TRIPASS_BEGIN_RENDER))
        self.AddStep("END_RENDERING", trinity.TriStepRenderPass(self.GetScene(), trinity.TRIPASS_END_RENDER))
        self.AddStep("RENDER_MAIN_PASS", trinity.TriStepRenderPass(self.GetScene(), trinity.TRIPASS_MAIN_RENDER))
        self.AddStep("SET_PERFRAME_DATA", trinity.TriStepRenderPass(self.GetScene(), trinity.TRIPASS_SET_PERFRAME_DATA))
        self._CreateDepthPass()
        self._CreateBackgroundStep()
        

        # We need the standard clear
        self.AddStep("CLEAR", trinity.TriStepClear((0.0,0.0,0.0,0.0), 1.0))
        
        # Setup tools steps if we have a tools scene
        if self.clientToolsScene is not None:
            self.SetClientToolsScene(self.clientToolsScene.object)


    def DoReleaseResources(self, level):
        """
        This function is called when the device is lost.
        """
        self.prepared = False

        self.hdrEnabled = False
        self.usePostProcessing = False
        self.shadowQuality = 0
        
        self.shadowMap = None
        
        self.depthTexture = None
                               
        self.renderTargetList = None
        self.customBackBuffer = None
        self.customDepthStencil = None
        self.depthTexture = None
        self.blitTexture = None

        self.distortionTexture = None

        self.postProcessingJob.Release()
        self.distortionJob.Release()
        self.backgroundDistortionJob.Release()
        self.sceneDesaturation.Disable()
        self.distortionJob.SetPostProcessVariable("Distortion", "TexDistortion", None)
        self.backgroundDistortionJob.SetPostProcessVariable("Distortion", "TexDistortion", None)

        self._SetDistortionMap()

        self._RefreshRenderTargets()


    def NotifyResourceCreationFailed(self):
        import localization
        eve.Message("CustomError", {"error": localization.GetByLabel("UI/Shared/VideoMemoryError")})


    def _GetSettings(self):
        """
        Returns a dictionary of settings keys and their values.
        The required keys and value combinations are:
         - hdrEnabled : True, False
         - postProcessingQuality : 0 to 2
         - shadowQuality : 0 to 2
         - aaQuality : 0 to 3
        """
        currentSettings = {}

        currentSettings["hdrEnabled"] = gfxsettings.Get(gfxsettings.GFX_HDR_ENABLED)
        currentSettings["postProcessingQuality"] = gfxsettings.Get(gfxsettings.GFX_POST_PROCESSING_QUALITY)
        currentSettings["shadowQuality"] = gfxsettings.Get(gfxsettings.GFX_SHADOW_QUALITY)
        currentSettings["aaQuality"] = gfxsettings.Get(gfxsettings.GFX_ANTI_ALIASING)

        return currentSettings


    def ApplyBaseSettings(self):
        currentSettings = self._GetSettings()

        self.bbFormat = _singletons.device.GetRenderContext().GetBackBufferFormat()
        self.postProcessingQuality = currentSettings["postProcessingQuality"]
        self.shadowQuality = currentSettings["shadowQuality"]
        self.aaQuality = currentSettings["aaQuality"]
        self.hdrEnabled = currentSettings["hdrEnabled"]

        self.distortionEffectsEnabled = self.useDepth = trinity.GetShaderModel().endswith("DEPTH")

        # Apply settings override, usually used by special case rendering(like the photo service)
        if "hdrEnabled" in self.overrideSettings:
            self.hdrEnabled = self.overrideSettings["hdrEnabled"]
        if "bbFormat" in self.overrideSettings:
            self.bbFormat = self.overrideSettings["bbFormat"]
        if "aaQuality" in self.overrideSettings:
            self.aaQuality = self.overrideSettings["aaQuality"]


    def OverrideSettings(self, key, value):
        self.overrideSettings[key] = value


    def _CreateRenderTargets(self):
        if not self.prepared:
            return

        width, height = self.GetBackBufferSize()
        dsFormatAL = _singletons.device.depthStencilFormat

        # customBackBuffer
        useCustomBackBuffer = self.hdrEnabled or self.msaaEnabled or self.fxaaEnabled
        customFormat = trinity.PIXEL_FORMAT.R16G16B16A16_FLOAT if self.hdrEnabled else self.bbFormat
        # make sure we don't use self.msaaType for comparing rendertargets in case we switch to fxaa.
        # 1 is the default Tr2RenderTarget multiSampleType for non-multisampled render targets.
        msaaType = self.msaaType if self.msaaEnabled else 1

        if useCustomBackBuffer and self._TargetDiffers(self.customBackBuffer, "trinity.Tr2RenderTarget", customFormat, msaaType, width, height):
            if self.msaaEnabled:
                self.customBackBuffer = rtm.GetRenderTargetMsaaAL(width, height, customFormat, msaaType, 0)
            else:
                self.customBackBuffer = rtm.GetRenderTargetAL(width, height, 1, customFormat)
            if self.customBackBuffer is not None:
                self.customBackBuffer.name = 'sceneRenderJobSpace.customBackBuffer'
        elif not useCustomBackBuffer:
            self.customBackBuffer = None
        
        # customDepthStencil
        if self.msaaEnabled and self._TargetDiffers(self.customDepthStencil, "trinity.Tr2DepthStencil", dsFormatAL, msaaType, width, height):
                self.customDepthStencil = rtm.GetDepthStencilAL(width, height, dsFormatAL, msaaType)
        elif not self.msaaEnabled:
            self.customDepthStencil = None

        # depthTexture
        if self.useDepth:
            if _singletons.platform == 'dx11':
                if self.customDepthStencil is not None:
                    self.depthTexture = self.customDepthStencil
                elif self._TargetDiffers(self.depthTexture, "trinity.Tr2DepthStencil", trinity.DEPTH_STENCIL_FORMAT.READABLE, 0, width, height):
                    self.depthTexture = rtm.GetDepthStencilAL(width, height, trinity.DEPTH_STENCIL_FORMAT.READABLE)
                    if self.depthTexture is not None and self.depthTexture.IsReadable():
                        self.depthTexture.name = 'sceneRenderJobSpace.depthTexture'
                    else:
                        self.depthTexture = None
            elif self._TargetDiffers(self.depthTexture, "trinity.Tr2DepthStencil", trinity.DEPTH_STENCIL_FORMAT.READABLE, 0, width, height):
                self.depthTexture = rtm.GetDepthStencilAL(width, height, trinity.DEPTH_STENCIL_FORMAT.READABLE)
                if self.depthTexture is not None and self.depthTexture.IsReadable():
                    self.depthTexture.name = 'sceneRenderJobSpace.depthTexture'
                else:
                    self.depthTexture = None
        else:
            self.depthTexture = None

        # blitTexture
        useBlitTexture = (self.usePostProcessing or self.distortionEffectsEnabled)
        useBlitTexture = useBlitTexture or (self.hdrEnabled and self.msaaEnabled)
        blitFormat = trinity.PIXEL_FORMAT.R16G16B16A16_FLOAT if self.hdrEnabled else self.bbFormat
        if useBlitTexture and self._TargetDiffers(self.blitTexture, "trinity.Tr2RenderTarget", blitFormat, 0, width, height):
            self.blitTexture = rtm.GetRenderTargetAL(width, height, 1, blitFormat, index = 1)
            if self.blitTexture is not None:
                self.blitTexture.name = 'sceneRenderJobSpace.blitTexture'
        elif not useBlitTexture:
            self.blitTexture = None

        # distortionTexture
        if self.distortionEffectsEnabled:
            index = 0
            if self.fxaaEnabled and self.bbFormat == trinity.PIXEL_FORMAT.B8G8R8A8_UNORM and not self.hdrEnabled:
                if useBlitTexture:
                    index = 2
                else:
                    index = 1
            if self._TargetDiffers(self.distortionTexture, "trinity.Tr2RenderTarget", 
                                   trinity.PIXEL_FORMAT.B8G8R8A8_UNORM, 0, width, height):
                self.distortionTexture = rtm.GetRenderTargetAL(
                    width, height, 1,
                    trinity.PIXEL_FORMAT.B8G8R8A8_UNORM,
                    index)
                if self.distortionTexture:
                    self.distortionTexture.name = 'sceneRenderJobSpace.distortionTexture'
            self._SetDistortionMap()
        else:
            self.distortionTexture = None
            self._SetDistortionMap()


    def _TargetDiffers(self, target, blueType, format, msType=0, width=0, height=0):
        if target is None:
            return True
        
        if blueType != target.__bluetype__:
            return True

        if format != target.format:
            return True

        multiSampleType = getattr(target, "multiSampleType", None)
        if multiSampleType is not None and multiSampleType != msType:
            return True

        if width != 0 and target.width != width:
            return True

        if height != 0 and target.height != height:
            return True

        return False


    def _RefreshRenderTargets(self):
        self.renderTargetList = ( 
                    blue.BluePythonWeakRef(self.customBackBuffer), 
                    blue.BluePythonWeakRef(self.customDepthStencil), 
                    blue.BluePythonWeakRef(self.depthTexture),
                    blue.BluePythonWeakRef(self.blitTexture),
                    blue.BluePythonWeakRef(self.distortionTexture),
                )
        renderTargets = (x.object for x in self.renderTargetList)
        self.SetRenderTargets(*renderTargets)


    def _RefreshAntiAliasing(self):
        if "aaQuality" not in self.overrideSettings:
            self.antiAliasingQuality = self.aaQuality = gfxsettings.Get(gfxsettings.GFX_ANTI_ALIASING)

        # Graphics Settings: Again, avoiding this call would be preferrable, 
        # perhaps a util function in evegraphics
        self.msaaType = self._GetMSAATypeFromQuality(self.antiAliasingQuality)
        self.fxaaQuality = self._GetFXAAQuality(self.antiAliasingQuality)

        if self.useFXAA:
            self.EnableFXAA(self.antiAliasingEnabled)
        else:
            self.EnableMSAA(self.antiAliasingEnabled)


    def UseFXAA(self, flag):
        self.useFXAA = flag

        if self.useFXAA:
            self.EnableMSAA(False)
        else:
            self.EnableFXAA(False)

        self._RefreshAntiAliasing()


    def EnableDistortionEffects(self, enable):
        self.distortionEffectsEnabled = enable


    def EnableAntiAliasing(self, enable):
        self.antiAliasingEnabled = enable
        self._RefreshAntiAliasing()


    def EnableFXAA(self, enable):
        self.fxaaEnabled = enable

        if not self.prepared:
            return
            
        if enable:
            if getattr(self, "fxaaEffect", None) is None:
                self.fxaaEffect = trinity.Tr2ShaderMaterial()
                self.fxaaEffect.highLevelShaderName = "PostProcess"
            self.fxaaEffect.defaultSituation = self.fxaaQuality
            self.fxaaEffect.BindLowLevelShader([])

            self.AddStep("FXAA", trinity.TriStepRenderFullScreenShader(self.fxaaEffect))
            if not self.usePostProcessing:
                self.AddStep("FXAA_CLEAR", trinity.TriStepClear((0,0,0,1), 1.0))
            self.RemoveStep("FINAL_BLIT")
        else:
            self.RemoveStep("FXAA")
            self.RemoveStep("FXAA_CLEAR")

        if not self.enabled:
            return
            
        self._CreateRenderTargets()
        self._RefreshRenderTargets()


    def EnableMSAA(self, enable):
        self.msaaEnabled = enable

        if not self.prepared:
            return

        if not self.enabled:
            return

        self._CreateRenderTargets()
        self._RefreshRenderTargets()


    def DoPrepareResources(self):
        """
        This function is called when the device is restored. 
        This function may raise exceptions attempting to create resources!
        """
        if not self.enabled or not self.canCreateRenderTargets:
            return

        try:
            self.prepared = True
            self.SetSettingsBasedOnPerformancePreferences()
        except trinity.D3DERR_OUTOFVIDEOMEMORY:
            logger.exception('Caught exception')
            self.DoReleaseResources(1)
            self._RefreshRenderTargets()
            uthread.new(self.NotifyResourceCreationFailed)


    def _GetFXAAQuality(self, quality):
        if quality == 3:
            return "FXAA_High"
        elif quality == 2:
            return "FXAA_Medium"
        elif quality == 1:
            return "FXAA_Low"

        return ""


    def _GetMSAATypeFromQuality(self, aaQuality):
        msaaType = 8
        try:
            if sm.IsServiceRunning("device"):
                msaaType = sm.GetService("device").GetMSAATypeFromQuality(aaQuality)
        except NameError:
            pass

        return msaaType


    def _SetSettingsBasedOnPerformancePreferences(self):
        self.antiAliasingEnabled = self.aaQuality > 0
        self.antiAliasingQuality = self.aaQuality


        self.msaaType = self._GetMSAATypeFromQuality(self.aaQuality)
        self.fxaaQuality = self._GetFXAAQuality(self.aaQuality)

        if self.shadowQuality > 0 and self.shadowMap is None:
            self.shadowMap = trinity.TriShadowMap()
        elif self.shadowQuality == 0:
            self.shadowMap = None

        if self.postProcessingQuality == 1:
            self.postProcessingJob.AddPostProcess(evePostProcess.POST_PROCESS_BLOOM_LOW)
            self.postProcessingJob.RemovePostProcess(evePostProcess.POST_PROCESS_BLOOM_HIGH)
            self.sceneDesaturation.Enable()
        elif self.postProcessingQuality == 2:
            self.postProcessingJob.AddPostProcess(evePostProcess.POST_PROCESS_BLOOM_HIGH)
            self.postProcessingJob.RemovePostProcess(evePostProcess.POST_PROCESS_BLOOM_LOW)
            self.sceneDesaturation.Enable()
        else:
            self.postProcessingJob.RemovePostProcess(evePostProcess.POST_PROCESS_BLOOM_HIGH)
            self.postProcessingJob.RemovePostProcess(evePostProcess.POST_PROCESS_BLOOM_LOW)
            self.sceneDesaturation.Disable()


    def SetSettingsBasedOnPerformancePreferences(self):
        if not self.enabled:
            return

        self.ApplyBaseSettings()

        # Populate derived values from base settings
        self._SetSettingsBasedOnPerformancePreferences()
        
        self.usePostProcessing = self.postProcessingQuality > 0
        self.doDepthPass = (not self.useFXAA and self.msaaType > 1) or self.forceDepthPass

        if self.distortionEffectsEnabled:
            self.distortionJob.AddPostProcess("Distortion", "res:/fisfx/postprocess/distortion.red")
            self.backgroundDistortionJob.AddPostProcess("Distortion", "res:/fisfx/postprocess/distortion.red")

        self._RefreshAntiAliasing()
        self._CreateRenderTargets()
        self._RefreshRenderTargets()
        self.ApplyPerformancePreferencesToScene()


    def ApplyPerformancePreferencesToScene(self):
        self._SetShadowMap()
        self._SetDepthMap()
        self._SetDistortionMap()


    def SetMultiViewStage(self, stageKey): 
        self.currentMultiViewStageKey = stageKey


    def SetRenderTargets(self, customBackBuffer, customDepthStencil, depthTexture, blitTexture, distortionTexture):
        """
        Set the required buffers on all the the renderjob steps.
        If any of these steps are missing, they will obviously not get set.
        """
        self.RemoveStep("SET_DEPTH")

        if self.GetSwapChain() is not None:
            self.AddStep("SET_SWAPCHAIN_RT", trinity.TriStepSetRenderTarget(self.GetSwapChain().backBuffer))
            self.AddStep("SET_SWAPCHAIN_DEPTH", trinity.TriStepSetDepthStencil(self.GetSwapChain().depthStencilBuffer))
        else:
            self.RemoveStep("SET_SWAPCHAIN_RT")
            self.RemoveStep("SET_SWAPCHAIN_DEPTH")
            
        activePostProcessing = self.usePostProcessing and self.postProcessingJob.liveCount > 0
        if customBackBuffer is not None:
            self.AddStep("SET_CUSTOM_RT", trinity.TriStepPushRenderTarget(customBackBuffer))
            self.AddStep("SET_FINAL_RT", trinity.TriStepPopRenderTarget())

            if self.msaaEnabled and not activePostProcessing:
                if self.hdrEnabled:
                    self.AddStep("FINAL_BLIT", self._DoFormatConversionStep(blitTexture, customBackBuffer))
                else:
                    self.AddStep("FINAL_BLIT", trinity.TriStepResolve(self.GetBackBufferRenderTarget(), customBackBuffer))
            elif self.hdrEnabled and not activePostProcessing and not self.msaaEnabled:
                self.AddStep("FINAL_BLIT", self._DoFormatConversionStep(customBackBuffer))
            else:
                self.RemoveStep("FINAL_BLIT")

            if self.fxaaEnabled:
                self.AddStep("SET_VAR_GATHER", trinity.TriStepSetVariableStore("GatherMap", customBackBuffer))
                self.RemoveStep("FINAL_BLIT")
            else:
                self.RemoveStep("SET_VAR_GATHER")
        else:
            self.RemoveStep("SET_CUSTOM_RT")
            self.RemoveStep("FINAL_BLIT")
            self.RemoveStep("SET_FINAL_RT")
            self.RemoveStep("SET_VAR_GATHER")

        if customDepthStencil is not None:
            self.AddStep("SET_DEPTH", trinity.TriStepPushDepthStencil(customDepthStencil))
            self.AddStep("RESTORE_DEPTH", trinity.TriStepPopDepthStencil())
        else:
            self.RemoveStep("RESTORE_DEPTH")

        if self.depthTexture is not None:
            if not self.doDepthPass:
                self.AddStep("SET_DEPTH", trinity.TriStepPushDepthStencil(depthTexture))
                self.AddStep("RESTORE_DEPTH", trinity.TriStepPopDepthStencil())
            self._SetDepthMap()
            if self.depthTexture.multiSampleType > 1:
                self.AddStep("SET_VAR_DEPTH", trinity.TriStepSetVariableStore("DepthMap", trinity.TriTextureRes()))
                self.AddStep("SET_VAR_DEPTH_MSAA", trinity.TriStepSetVariableStore("DepthMapMsaa", depthTexture))
            else:
                self.AddStep("SET_VAR_DEPTH", trinity.TriStepSetVariableStore("DepthMap", depthTexture))
                self.AddStep("SET_VAR_DEPTH_MSAA", trinity.TriStepSetVariableStore("DepthMapMsaa", trinity.TriTextureRes()))
        else:
            if not self.msaaEnabled:
                self.RemoveStep("SET_DEPTH")
                self.RemoveStep("RESTORE_DEPTH")
            self.RemoveStep("SET_VAR_DEPTH")
            self.RemoveStep("SET_VAR_DEPTH_MSAA")

        self._RefreshPostProcessingJob(self.postProcessingJob, self.usePostProcessing and self.prepared)
        self._RefreshPostProcessingJob(self.distortionJob, self.distortionEffectsEnabled and self.prepared)
        self._RefreshPostProcessingJob(self.backgroundDistortionJob, self.distortionEffectsEnabled and self.prepared)

        if distortionTexture is not None:
            self.AddStep("DO_DISTORTIONS", trinity.TriStepRunJob(self.distortionJob))
            distortionTriTextureRes = trinity.TriTextureRes()
            distortionTriTextureRes.SetFromRenderTarget(distortionTexture)
            self.distortionJob.SetPostProcessVariable("Distortion", "TexDistortion", distortionTriTextureRes)
            self.backgroundDistortionJob.SetPostProcessVariable("Distortion", "TexDistortion", distortionTriTextureRes)
        else:
            self.RemoveStep("DO_DISTORTIONS")

        self._CreateDepthPass()

    def GetRenderTargets(self):   
        return self.renderTargetList

    def EnableSceneUpdate(self, isEnabled):
        if self.updateJob:
            if isEnabled:
                if len(self.updateJob.steps) == 0:
                    self.updateJob.steps.append(trinity.TriStepUpdate(self.GetScene()))
                    self.updateJob.steps[0].name = "UPDATE_SCENE"
                else:
                    self.updateJob.steps[0] = trinity.TriStepUpdate(self.GetScene())
            elif len(self.updateJob.steps) > 0:
                del self.updateJob.steps[0]
        else:
            if isEnabled:
                self.AddStep("UPDATE_SCENE", trinity.TriStepUpdate(self.GetScene()))
            else:
                self.RemoveStep("UPDATE_SCENE")
            
    def EnableVisibilityQuery( self, isEnabled ):
        pass


class SceneDesaturation(object):
    attrName = "SaturationFactor"


    def __init__(self, ppJob):
        self.ppJob = ppJob
        self._value = 1.0

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value
        self.ppJob.SetPostProcessVariable(evePostProcess.POST_PROCESS_DESATURATE, self.attrName, value)

    def Disable(self):
        self.ppJob.RemovePostProcess(evePostProcess.POST_PROCESS_DESATURATE)

    def Enable(self):
        self.ppJob.AddPostProcess(evePostProcess.POST_PROCESS_DESATURATE)
