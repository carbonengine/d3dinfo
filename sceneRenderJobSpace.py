import logging
import blue
import evegraphics.settings as gfxsettings

from . import _trinity as trinity
from . import _singletons
from .renderJob import CreateRenderJob
from .sceneRenderJobBase import SceneRenderJobBase
from .renderJobUtils import renderTargetManager as rtm
from . import evePostProcess

DEFAULT_POSTPROCESS_PATH = 'res:/fisfx/postprocess/DefaultPostProcessingSettings.red'

logger = logging.getLogger(__name__)


def CreateSceneRenderJobSpace(name=None, stageKey=None):
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
        "SET_UPDATE_VIEW",
        "SET_UPDATE_PROJECTION",
        "SET_CUSTOM_RT",
        "SET_DEPTH",
        "SET_VAR_DEPTH",
        "SET_VAR_DEPTH_MSAA",
        "SET_VIEWPORT",
        "CAMERA_UPDATE",
        "SET_PROJECTION",
        "SET_VIEW",
        "UPDATE_PHYSICS",
        "UPDATE_SCENE",
        "UPDATE_BRACKETS",
        "CLEAR",
        "BEGIN_RENDER",
        "RENDER_BACKGROUND",
        "DO_BACKGROUND_DISTORTIONS",
        "RENDER_DEPTH_PASS",
        "RENDER_MAIN_PASS",
        "DO_DISTORTIONS",
        "END_RENDERING",
        "SET_UI_PROJECTION",
        "SET_UI_VIEW",
        "RENDER_3D_UI",
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
        "FPS_COUNTER"
    ]

    # This is a template for creating quad and multi-view renderjobs
    # it breaks things down into passes, with shared steps in between
    multiViewStages = []

    visualizations = []

    renderTargetList = []

    def _ManualInit(self, name="SceneRenderJobSpace"):
        """
        Decorated classes cannot use a normal init function, so this must be called manually
        This version is called from ManualInit on SceneRenderJobBase
        """
        # Active scenes
        self.scene = None
        self.clientToolsScene = None

        # The active camera, this ref might be unneccessary, keep in mind failure to reset
        self.camera = None

        # All the surfaces needed for different settings
        self.customBackBuffer = None
        self.customDepthStencil = None
        self.depthTexture = None
        self.blitTexture = None
        self.distortionTexture = None
        self.velocityTexture = None
        self.accumulationBuffer = None

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
        self.aaQuality = 0
        self.useTAA = True
        self.msaaEnabled = False
        self.doDepthPass = False
        self.forceDepthPass = False
        self.msaaType = 4

        self.distortionEffectsEnabled = False
        self.secondaryLighting = False

        self.taaEnabled = False
        self.taaPixelOffset = 0.5
        self.taaPattern = 3

        self.postProcessingQuality = 0

        self.bbFormat = _singletons.device.GetRenderContext().GetBackBufferFormat()

        self.prepared = False

        self._enablePostProcessing = True

        self.distortionJob = evePostProcess.EvePostProcessingJob()
        self.backgroundDistortionJob = evePostProcess.EvePostProcessingJob()

        self.overrideSettings = {}

        self.SetSettingsBasedOnPerformancePreferences()

        self.updateJob = CreateRenderJob(name + "_Update")
        self.updateJob.scheduled = False

        self.gpuParticlesEnabled = True

        self.useImpostors = True

    def Enable(self, schedule=True):
        SceneRenderJobBase.Enable(self, schedule)
        self.SetSettingsBasedOnPerformancePreferences()

    def SuspendRendering(self):
        SceneRenderJobBase.UnscheduleRecurring(self)
        self.scheduled = False
        self.EnableGpuEmission(False)

    def Start(self):
        SceneRenderJobBase.Start(self)
        self.EnableGpuEmission(True)
        self.ScheduleUpdateJob()

    def ScheduleUpdateJob(self):
        if self.updateJob is not None and not self.updateJob.scheduled:
            self.updateJob.ScheduleUpdate()
            self.updateJob.scheduled = True

    def EnableGpuEmission(self, enable):
        if not self.gpuParticlesEnabled:
            return

        scene = self.GetScene()
        if scene is None:
            return

        if scene.gpuParticleSystem is not None:
            scene.gpuParticleSystem.enableEmit = enable

    def Disable(self):
        SceneRenderJobBase.Disable(self)
        self.UnscheduleUpdateJob()

    def UnscheduleUpdateJob(self):
        if self.updateJob is not None and self.updateJob.scheduled:
            self.updateJob.UnscheduleUpdate()
            self.updateJob.scheduled = False

    def UnscheduleRecurring(self, scheduledRecurring=None):
        SceneRenderJobBase.UnscheduleRecurring(self, scheduledRecurring)
        self.UnscheduleUpdateJob()

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

    def SetCameraView(self, view):
        super(SceneRenderJobSpace, self).SetCameraView(view)
        self._SetUpdateStep(trinity.TriStepSetView(view), "SET_VIEW")
        self.AddStep(trinity.TriStepSetView(view), "SET_UI_VIEW")

    def SetCameraProjection(self, proj):
        super(SceneRenderJobSpace, self).SetCameraProjection(proj)
        self._SetUpdateStep(trinity.TriStepSetProjection(proj), "SET_PROJECTION")
        self.AddStep(trinity.TriStepSetProjection(proj), "SET_UI_PROJECTION")

    def SetCameraCallback(self, cb):
        if self.updateJob is not None and self.updateJob.scheduled:
            self._SetUpdateStep(trinity.TriStepPythonCB(cb), "CAMERA_UPDATE")
        else:
            self.AddStep("CAMERA_UPDATE", trinity.TriStepPythonCB(cb))

    def SetActiveCamera(self, camera=None, view=None, projection=None):
        """
        This call adds or removes the steps nessecary for controlling the camera
        depending on if 'camera' is None
        """
        if camera is None and view is None and projection is None:
            self.RemoveStep("SET_VIEW")
            self.RemoveStep("SET_PROJECTION")
            self.RemoveStep("SET_UPDATE_VIEW")
            self.RemoveStep("SET_UPDATE_PROJECTION")
            self.RemoveStep("SET_UI_VIEW")
            self.RemoveStep("SET_UI_PROJECTION")
            return

        if camera is not None:
            self.AddStep("SET_VIEW", trinity.TriStepSetView(None, camera))
            self.AddStep("SET_UPDATE_VIEW", trinity.TriStepSetView(None, camera))
            self.AddStep("SET_UI_VIEW", trinity.TriStepSetView(None, camera))
            self._SetUpdateStep(trinity.TriStepSetView(None, camera), "SET_VIEW")
            self.AddStep("SET_PROJECTION", trinity.TriStepSetProjection(camera.projectionMatrix))
            self.AddStep("SET_UPDATE_PROJECTION", trinity.TriStepSetProjection(camera.projectionMatrix))
            self._SetUpdateStep(trinity.TriStepSetProjection(camera.projectionMatrix), "SET_PROJECTION")
        if view is not None:
            self.AddStep("SET_VIEW", trinity.TriStepSetView(view))
            self.AddStep("SET_UI_VIEW", trinity.TriStepSetView(view))
            self.AddStep("SET_UPDATE_VIEW", trinity.TriStepSetView(view))
            self._SetUpdateStep(trinity.TriStepSetView(view), "SET_VIEW")
        if projection is not None:
            self.AddStep("SET_PROJECTION", trinity.TriStepSetProjection(projection))
            self.AddStep("SET_UI_PROJECTION", trinity.TriStepSetProjection(projection))
            self.AddStep("SET_UPDATE_PROJECTION", trinity.TriStepSetProjection(projection))
            self._SetUpdateStep(trinity.TriStepSetProjection(projection), "SET_PROJECTION")

    def SetActiveScene(self, scene, key=None):
        """
        This function sets the scene and the scene key associated with it
        """
        self.SetScene(scene)

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

    def _SetVelocityMap(self):
        """
        Set velocity map to the scene
        """
        if not self.enabled:
            return
        if self.GetScene() is None:
            return

        if hasattr(self.GetScene(), "velocityMap"):
            self.GetScene().velocityMap = self.velocityTexture

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

    def _SetSecondaryLighting(self):
        scene = self.GetScene()
        if scene is None:
            return
        if self.secondaryLighting:
            if not scene.shLightingManager:
                scene.shLightingManager = trinity.Tr2ShLightingManager()
                scene.shLightingManager.primaryIntensity = gfxsettings.SECONDARY_LIGHTING_INTENSITY
                scene.shLightingManager.secondaryIntensity = gfxsettings.SECONDARY_LIGHTING_INTENSITY
        else:
            scene.shLightingManager = None

    def ForceDepthPass(self, enabled):
        """ Force a special depth pass under SM_3_0_DEPTH """
        self.forceDepthPass = enabled

    def _RefreshPostProcessingJob(self, job, enabled):
        if enabled:
            job.Prepare(self._GetSourceRTForPostProcessing(), self.blitTexture,
                        destination=self._GetDestinationRTForPostProcessing())
            job.CreateSteps()
        else:
            job.Release()

    def _GetSourceRTForPostProcessing(self):
        if self.customBackBuffer is not None:
            return self.customBackBuffer
        return self.GetBackBufferRenderTarget()

    def _GetDestinationRTForPostProcessing(self):
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

        if self.enabled and self.doDepthPass and self.depthTexture is not None:
            rj.steps.append(trinity.TriStepPushViewport())
            if not _singletons.platformInfo.GetStaticCap(trinity.PlatformStaticCap.MSAA_SAMPLE):
                rj.steps.append(trinity.TriStepPushRenderTarget(self._GetRTForDepthPass()))
            rj.steps.append(trinity.TriStepPushDepthStencil(self.depthTexture))
            # This amazing viewport foo is currently the cleanest way to guarantee correct viewports
            # in the client, embedded jobs, maya and tp2.
            rj.steps.append(trinity.TriStepPopViewport())
            rj.steps.append(trinity.TriStepPushViewport())
            rj.steps.append(trinity.TriStepRenderPass(self.GetScene(), trinity.TRIPASS_DEPTH_PASS))
            rj.steps.append(trinity.TriStepPopDepthStencil())
            if not _singletons.platformInfo.GetStaticCap(trinity.PlatformStaticCap.MSAA_SAMPLE):
                rj.steps.append(trinity.TriStepPopRenderTarget())
            rj.steps.append(trinity.TriStepPopViewport())

        self.AddStep("RENDER_DEPTH_PASS", trinity.TriStepRunJob(rj))

    def _FindUpdateStep(self, key):
        for each in self.updateJob.steps:
            if each.name == key:
                return each

    def _CreateUpdateStep(self, step, name):
        self.updateJob.steps.append(step)
        step.name = name

    def _CreateUpdateSteps(self):
        self._CreateUpdateStep(trinity.TriStepPushViewport(), "PUSH_VIEWPORT")
        self._CreateUpdateStep(trinity.TriStepSetViewport(), "SET_VIEWPORT")
        self._CreateUpdateStep(trinity.TriStepPythonCB(), "CAMERA_UPDATE")
        self._CreateUpdateStep(trinity.TriStepSetView(), "SET_VIEW")
        self._CreateUpdateStep(trinity.TriStepSetProjection(), "SET_PROJECTION")
        self._CreateUpdateStep(trinity.TriStepPopViewport(), "POP_VIEWPORT")

    def SetBracketCurveSet(self, cs):
        self.SetStepAttr("UPDATE_BRACKETS", 'object', cs)

    def _SetUpdateStep(self, step, name):
        if self.updateJob is None:
            return
        step.name = name
        idx = None
        for i, each in enumerate(self.updateJob.steps):
            if each.name == name:
                idx = i
                break
        if idx is None:
            raise KeyError('Update step is not found')
        self.updateJob.steps[idx] = step

    def _SetScene(self, scene):
        """
        Sets a scene into the render job
        """
        if scene is not None and scene.postprocess is None and hasattr(scene, "postprocess"):
            scene.postprocess = trinity.Load(DEFAULT_POSTPROCESS_PATH)

        self._SetTaaToRenderJobState()
        self.ModifyPostProcessForPerformance()

        self.SetStepAttr("FINAL_BLIT", 'scene', scene)

        self.SetStepAttr("UPDATE_SCENE", 'object', scene)
        self.SetStepAttr("RENDER_MAIN_PASS", 'scene', scene)
        self.SetStepAttr("BEGIN_RENDER", 'scene', scene)
        self.SetStepAttr("END_RENDERING", 'scene', scene)
        self.SetStepAttr("SET_PERFRAME_DATA", 'scene', scene)
        self.SetStepAttr("RENDER_3D_UI", 'scene', scene)
        self.SetStepAttr("RENDER_BACKGROUND", 'scene', scene)
        self.SetStepAttr("DO_BACKGROUND_DISTORTIONS", 'predicate', scene)
        self.SetStepAttr("DO_DISTORTIONS", 'predicate', scene)
        self._CreateDepthPass()

        self.ApplyPerformancePreferencesToScene()

        if scene is not None and (self.customBackBuffer is not None or self.taaEnabled):
            finalBlitStep = self.AddStep("FINAL_BLIT", trinity.TriStepRenderPostProcess(scene, self._GetSourceRTForPostProcessing()))
            finalBlitStep.quality = self.postProcessingQuality


    def _SetTaaToRenderJobState(self):
        scene = self.GetScene()
        if scene is not None and scene.postprocess is not None and self.taaEnabled:
            scene.postprocess.taa = trinity.Tr2PPTaaEffect()

    def _CreateBasicRenderSteps(self):
        # Scene update and render
        if self.updateJob is not None:
            if len(self.updateJob.steps) == 0:
                self._CreateUpdateSteps()
        scene = self.GetScene()
        self.AddStep("UPDATE_SCENE", trinity.TriStepUpdate(scene))
        self.AddStep("UPDATE_BRACKETS", trinity.TriStepUpdate())
        self.AddStep("SET_VIEWPORT", trinity.TriStepSetViewport())
        self.AddStep("BEGIN_RENDER", trinity.TriStepRenderPass(scene, trinity.TRIPASS_BEGIN_RENDER))
        self.AddStep("END_RENDERING", trinity.TriStepRenderPass(scene, trinity.TRIPASS_END_RENDER))
        self.AddStep("RENDER_MAIN_PASS", trinity.TriStepRenderPass(scene, trinity.TRIPASS_MAIN_RENDER))
        self.AddStep("SET_PERFRAME_DATA", trinity.TriStepRenderPass(scene, trinity.TRIPASS_SET_PERFRAME_DATA))
        self.AddStep("RENDER_3D_UI", trinity.TriStepRenderPass(scene, trinity.TRIPASS_RENDER_UI))
        self._CreateDepthPass()
        self.AddStep("RENDER_BACKGROUND", trinity.TriStepRenderPass(scene, trinity.TRIPASS_BACKGROUND_RENDER))
        self.AddStep("DO_BACKGROUND_DISTORTIONS",
                     trinity.TriStepPredicated("hasBackgroundDistortionBatches",
                                               scene,
                                               trinity.TriStepRunJob(self.backgroundDistortionJob)))

        # We need the standard clear
        self.AddStep("CLEAR", trinity.TriStepClear((0.0, 0.0, 0.0, 0.0), 0.0))

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
        self.accumulationBuffer = None
        self.velocityTexture = None

        self.distortionJob.Release()
        self.backgroundDistortionJob.Release()
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

        currentSettings["postProcessingQuality"] = self.overrideSettings.get(gfxsettings.GFX_POST_PROCESSING_QUALITY,
                                                                             gfxsettings.Get(
                                                                                 gfxsettings.GFX_POST_PROCESSING_QUALITY))
        currentSettings["shadowQuality"] = gfxsettings.Get(gfxsettings.GFX_SHADOW_QUALITY)
        currentSettings["aaQuality"] = gfxsettings.Get(gfxsettings.GFX_ANTI_ALIASING)
        try:
            currentSettings["gpuParticles"] = gfxsettings.Get(gfxsettings.UI_GPU_PARTICLES_ENABLED)
        except gfxsettings.UninitializedSettingsGroupError:
            currentSettings["gpuParticles"] = gfxsettings.GetDefault(gfxsettings.UI_GPU_PARTICLES_ENABLED)

        return currentSettings

    def ApplyBaseSettings(self):
        currentSettings = self._GetSettings()

        self.bbFormat = _singletons.device.GetRenderContext().GetBackBufferFormat()
        self.postProcessingQuality = currentSettings["postProcessingQuality"]
        self.shadowQuality = currentSettings["shadowQuality"]
        self.aaQuality = currentSettings["aaQuality"]
        self.hdrEnabled = self.postProcessingQuality > 0
        self.gpuParticlesEnabled = currentSettings.get("gpuParticles", True)

        isDepth = trinity.GetShaderModel().endswith("DEPTH")
        self.secondaryLighting = self.distortionEffectsEnabled = isDepth
        self.useDepth = isDepth or _singletons.platformInfo.GetStaticCap(trinity.PlatformStaticCap.MSAA_SAMPLE)

        trinity.settings.SetValue('eveSpaceSceneDynamicLighting',
                                  trinity.GetShaderModel().endswith("DEPTH") and _singletons.platformInfo.GetStaticCap(
                                      trinity.PlatformStaticCap.COMPUTE))

        # Apply settings override, usually used by special case rendering(like the photo service)
        if "bbFormat" in self.overrideSettings:
            self.bbFormat = self.overrideSettings["bbFormat"]
        if "aaQuality" in self.overrideSettings:
            self.aaQuality = self.overrideSettings["aaQuality"]

    def OverrideSettings(self, key, value):
        self.overrideSettings[key] = value

    def StopOverrideSettings(self, key):
        try:
            del self.overrideSettings[key]
        except KeyError:
            pass

    def _CreateRenderTargets(self):
        if not self.prepared:
            return

        width, height = self.GetBackBufferSize()

        # customBackBuffer
        useCustomBackBuffer = self.hdrEnabled or self.msaaEnabled
        if self.hdrEnabled:
            if _singletons.device.SupportsRenderTargetFormat(trinity.PIXEL_FORMAT.R11G11B10_FLOAT):
                customFormat = trinity.PIXEL_FORMAT.R11G11B10_FLOAT
            else:
                customFormat = trinity.PIXEL_FORMAT.R16G16B16A16_FLOAT
        else:
            customFormat = self.bbFormat
        # 1 is the default Tr2RenderTarget multiSampleType for non-multisampled render targets.
        msaaType = self.msaaType if self.msaaEnabled else 1
        if _singletons.device.SupportsDepthStencilFormat(
                trinity.DEPTH_STENCIL_FORMAT.D32F) and _singletons.platformInfo.GetStaticCap(
                trinity.PlatformStaticCap.MSAA_SAMPLE):
            dsFormatAL = trinity.DEPTH_STENCIL_FORMAT.D32F
        elif self.useDepth and msaaType <= 1:
            dsFormatAL = trinity.DEPTH_STENCIL_FORMAT.READABLE
        else:
            dsFormatAL = trinity.DEPTH_STENCIL_FORMAT.D24S8

        if useCustomBackBuffer and self._TargetDiffers(self.customBackBuffer, "trinity.Tr2RenderTarget", customFormat,
                                                       msaaType, width, height):
            if self.msaaEnabled:
                self.customBackBuffer = rtm.GetRenderTargetMsaaAL(width, height, customFormat, msaaType, 0)
            else:
                self.customBackBuffer = rtm.GetRenderTargetAL(width, height, 1, customFormat)
            if self.customBackBuffer is not None:
                self.customBackBuffer.name = 'sceneRenderJobSpace.customBackBuffer'
        elif not useCustomBackBuffer:
            self.customBackBuffer = None

        # customDepthStencil
        self.customDepthStencil = rtm.GetDepthStencilAL(width, height, dsFormatAL, msaaType)

        # depthTexture
        if self.useDepth:
            if _singletons.platformInfo.GetStaticCap(trinity.PlatformStaticCap.MSAA_SAMPLE):
                self.depthTexture = self.customDepthStencil
            elif msaaType > 1:
                self.depthTexture = rtm.GetDepthStencilAL(width, height, trinity.DEPTH_STENCIL_FORMAT.READABLE)
                self.depthTexture.name = 'sceneRenderJobSpace.depthTexture'
            else:
                self.depthTexture = self.customDepthStencil
        else:
            self.depthTexture = None

        # blitTexture
        useBlitTexture = (self.usePostProcessing or self.distortionEffectsEnabled or self.taaEnabled)
        useBlitTexture = useBlitTexture or (self.hdrEnabled and self.msaaEnabled)
        blitFormat = customFormat
        if useBlitTexture and self._TargetDiffers(self.blitTexture, "trinity.Tr2RenderTarget", blitFormat, 0, width,
                                                  height):
            self.blitTexture = rtm.GetRenderTargetAL(width, height, 1, blitFormat, index=1)
            if self.blitTexture is not None:
                self.blitTexture.name = 'sceneRenderJobSpace.blitTexture'
        elif not useBlitTexture:
            self.blitTexture = None

        # distortionTexture
        if self.distortionEffectsEnabled:
            index = 0
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
            blue.BluePythonWeakRef(self.accumulationBuffer),
        )
        renderTargets = (x.object for x in self.renderTargetList)
        self.SetRenderTargets(*renderTargets)

    def _RefreshAntiAliasing(self):
        if "aaQuality" not in self.overrideSettings:
            self.msaaQuality = self._GetMSAAQualityFromAAQuality(gfxsettings.Get(gfxsettings.GFX_ANTI_ALIASING))

        taaEnabled = gfxsettings.IsTAAEnabled(gfxsettings.Get(gfxsettings.GFX_ANTI_ALIASING) and self.postProcessingQuality > 0)
        self.taaEnabled = taaEnabled and _singletons.platformInfo.GetStaticCap(
            trinity.PlatformStaticCap.TAA) and trinity.GetShaderModel().endswith("DEPTH") and self.useTAA

        # Graphics Settings: Again, avoiding this call would be preferrable,
        # perhaps a util function in evegraphics
        self.msaaType = self._GetMSAATypeFromQuality(self.aaQuality)
        self.EnableMSAA(self.antiAliasingEnabled)

    def EnableDistortionEffects(self, enable):
        self.distortionEffectsEnabled = enable

    def EnableAntiAliasing(self, enable):
        self.antiAliasingEnabled = enable
        self._RefreshAntiAliasing()

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

    def _GetMSAAQualityFromAAQuality(self, aaQuality):
        qual = gfxsettings.AA_QUALITY_MSAA_HIGH
        try:
            if sm.IsServiceRunning("device"):
                qual = sm.GetService("device").GetMSAAQualityFromAAQuality(aaQuality)
        except NameError:
            pass

        return qual & gfxsettings.AA_QUALITY_MASK

    def _GetMSAATypeFromQuality(self, aaQuality):
        msaaType = 8
        try:
            if sm.IsServiceRunning("device"):
                msaaType = sm.GetService("device").GetMSAATypeFromQuality(aaQuality)
        except NameError:
            pass

        return msaaType

    def _SetSettingsBasedOnPerformancePreferences(self):
        self.msaaQuality = self._GetMSAAQualityFromAAQuality(self.aaQuality)
        self.antiAliasingEnabled = self.msaaQuality > 0
        self.msaaType = self._GetMSAATypeFromQuality(self.aaQuality)

        if self.shadowQuality > 0 and self.shadowMap is None:
            self.shadowMap = trinity.TriShadowMap()
        elif self.shadowQuality == 0:
            self.shadowMap = None

    def EnablePostProcessing(self, enable):
        self._enablePostProcessing = enable
        self.SetSettingsBasedOnPerformancePreferences()

    def SetSettingsBasedOnPerformancePreferences(self):
        if not self.enabled:
            return

        self.ApplyBaseSettings()

        # Populate derived values from base settings
        self._SetSettingsBasedOnPerformancePreferences()

        self.usePostProcessing = self.postProcessingQuality > 0
        if _singletons.platformInfo.GetStaticCap(trinity.PlatformStaticCap.MSAA_SAMPLE):
            self.doDepthPass = (trinity.GetShaderModel() != 'SM_3_0_LO') or self.forceDepthPass
        else:
            self.doDepthPass = (self.msaaType > 1) or self.forceDepthPass

        if self.distortionEffectsEnabled:
            self.distortionJob.AddPostProcess("Distortion", "res:/fisfx/postprocess/distortion.red")
            self.backgroundDistortionJob.AddPostProcess("Distortion", "res:/fisfx/postprocess/distortion.red")

        self._RefreshAntiAliasing()
        self._CreateRenderTargets()
        self._RefreshRenderTargets()

        self.ModifyPostProcessForPerformance()

        self.ApplyPerformancePreferencesToScene()

    def ModifyPostProcessForPerformance(self):
        if not self.enabled:
            return
        step = self.GetStep("FINAL_BLIT")
        if step is None:
            return
        step.quality = self.postProcessingQuality
        step.enabled = step.quality != 0 or self.antiAliasingEnabled

    def ApplyPerformancePreferencesToScene(self):
        self._SetShadowMap()
        self._SetDepthMap()
        self._SetDistortionMap()
        self._SetVelocityMap()
        self._SetSecondaryLighting()
        trinity.settings.SetValue('eveSpaceSceneDynamicLighting',
                                  trinity.GetShaderModel().endswith("DEPTH") and _singletons.platformInfo.GetStaticCap(
                                      trinity.PlatformStaticCap.COMPUTE))

        try:
            isHighQuality = gfxsettings.Get(gfxsettings.GFX_SHADER_QUALITY) == gfxsettings.SHADER_MODEL_HIGH
        except gfxsettings.UninitializedSettingsGroupError:
            isHighQuality = True

        scene = self.GetScene()
        if scene is None:
            return
        if self.useImpostors:
            scene.impostorManager = trinity.Tr2ImpostorManager()
        if self.gpuParticlesEnabled:
            if not scene.gpuParticleSystem:
                scene.gpuParticleSystem = blue.resMan.LoadObject('res:/fisfx/gpuparticles/system.red')
        else:
            scene.gpuParticleSystem = None
        if self.msaaEnabled:
            scene.msaaSamples = self.msaaType
        else:
            scene.msaaSamples = 1
        if _singletons.platform == 'dx11' and self.postProcessingQuality == 2:
            scene.nebulaBrightnessOverride = 0.3
        else:
            scene.nebulaBrightnessOverride = 0.0

        scene.reflectionProbe = trinity.Tr2ReflectionProbe() if isHighQuality else None

    def _GetPostProcessPSData(self):
        scene = self.GetScene()
        if scene is None:
            return None
        return scene.GetPostProcessPSBuffer()

    def SetMultiViewStage(self, stageKey):
        self.currentMultiViewStageKey = stageKey

    def SetRenderTargets(self, customBackBuffer, customDepthStencil, depthTexture, blitTexture, distortionTexture,
                         accumulationBuffer):
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

        if customBackBuffer is not None:
            self.AddStep("SET_CUSTOM_RT", trinity.TriStepPushRenderTarget(customBackBuffer))
            self.AddStep("SET_FINAL_RT", trinity.TriStepPopRenderTarget())
        else:
            self.RemoveStep("SET_CUSTOM_RT")
            self.RemoveStep("SET_FINAL_RT")

        if customBackBuffer is not None or self.taaEnabled:
            scene = self.GetScene()
            if scene is not None:
                if scene.postprocess:
                    if self.taaEnabled and scene.postprocess.taa is None:
                        scene.postprocess.taa = trinity.Tr2PPTaaEffect()
                    else:
                        scene.postprocess.taa = None

                self.AddStep("FINAL_BLIT",
                             trinity.TriStepRenderPostProcess(self.GetScene(), self._GetSourceRTForPostProcessing()))

        if customDepthStencil is not None:
            self.AddStep("SET_DEPTH", trinity.TriStepPushDepthStencil(customDepthStencil))
            self.AddStep("RESTORE_DEPTH", trinity.TriStepPopDepthStencil())
        else:
            self.RemoveStep("RESTORE_DEPTH")

        if self.depthTexture is not None:
            if not self.doDepthPass or _singletons.platformInfo.GetStaticCap(trinity.PlatformStaticCap.MSAA_SAMPLE):
                self.AddStep("SET_DEPTH", trinity.TriStepPushDepthStencil(depthTexture))
                self.AddStep("RESTORE_DEPTH", trinity.TriStepPopDepthStencil())
            self._SetDepthMap()
            if self.depthTexture.multiSampleType > 1:
                self.AddStep("SET_VAR_DEPTH", trinity.TriStepSetVariableStore("DepthMap", trinity.TriTextureRes()))
                self.AddStep("SET_VAR_DEPTH_MSAA", trinity.TriStepSetVariableStore("DepthMapMsaa", depthTexture))
            else:
                self.AddStep("SET_VAR_DEPTH", trinity.TriStepSetVariableStore("DepthMap", depthTexture))
                self.AddStep("SET_VAR_DEPTH_MSAA",
                             trinity.TriStepSetVariableStore("DepthMapMsaa", trinity.TriTextureRes()))
        else:
            self.RemoveStep("SET_VAR_DEPTH")
            self.RemoveStep("SET_VAR_DEPTH_MSAA")

        self._RefreshPostProcessingJob(self.distortionJob, self.distortionEffectsEnabled and self.prepared)
        self._RefreshPostProcessingJob(self.backgroundDistortionJob, self.distortionEffectsEnabled and self.prepared)

        if distortionTexture is not None:
            self.AddStep("DO_DISTORTIONS",
                         trinity.TriStepPredicated("hasForegroundDistortionBatches",
                                                   self.GetScene(),
                                                   trinity.TriStepRunJob(self.distortionJob)))
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
                    self._CreateUpdateSteps()
                else:
                    self._SetUpdateStep(trinity.TriStepUpdate(self.GetScene()), "UPDATE_SCENE")
            elif len(self.updateJob.steps) > 0:
                del self.updateJob.steps[0]
        else:
            if isEnabled:
                self.AddStep("UPDATE_SCENE", trinity.TriStepUpdate(self.GetScene()))
            else:
                self.RemoveStep("UPDATE_SCENE")

    def EnableVisibilityQuery(self, isEnabled):
        pass