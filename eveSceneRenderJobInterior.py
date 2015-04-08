import blue
import yaml
import geo2

import evegraphics.settings as gfxsettings

from . import _singletons
from . import _trinity as trinity
from .sceneRenderJobBase import SceneRenderJobBase
from .renderJobUtils import renderTargetManager as rtm
from . import renderSSAOJob


def CreateEveSceneRenderJobInterior(name=None, stageKey=None):
    """
    We can't use __init__ on a decorated class, so we provide a creation function that does it for us
    """
    newRJ = EveSceneRenderJobInterior()
    if name is not None:
        newRJ.ManualInit(name)
    else:
        newRJ.ManualInit()
    
    newRJ.SetMultiViewStage(stageKey)
    return newRJ
    

class EveSceneRenderJobInterior(SceneRenderJobBase):
    # This is a master list that we can refer to, when we want to insert steps that are not already in
    # the render steps, by looking for the prior or next step that exists, in order to position the new one
    # See: AddStep
    renderStepOrder = [
        "UPDATE_BACKGROUND_SCENE",
        "UPDATE_STEREO",
        "UPDATE_BACKGROUND_CAMERA",
        "UPDATE_UI",
        "SET_VIEWPORT",
        "SET_DEPTH",
        "SET_BACKGROUND_DEPTH_VAR",
        "SET_BACKGROUND_RT",
        "SET_BACKGROUND_PROJECTION",
        "SET_BACKGROUND_VIEW",
        "CLEAR_BACKGROUND_RT",
        "CLEAR_BACKGROUND_DEPTH",
        "RENDER_BACKGROUND_SCENE",
        "SET_PROJECTION",
        "SET_VIEW",
        "UPDATE_SCENE",
        "VISIBILITY_QUERY",    
        "FILTER_VISIBILITY_RESULT",
        "SET_VISIBILITY_RESULT",
        "SET_VISUALIZATION",
        "SET_PREPASS_RT",
        "CLEAR_PREPASS",
        "BEGIN_MANAGED_RENDERING",    
        "RENDER_PREPASS",
        "SET_LIGHT_RT",
        "CLEAR_LIGHTS",
        "SET_VAR_LIGHTS_DEPTH",
        "SET_VAR_LIGHTS_PREPASS",
        "SET_VAR_LIGHT_LUT",
        "SET_VAR_LIGHT_FRESNEL",
        "RENDER_LIGHTS",
        "RENDER_SSAO",
        "SET_VAR_SSAO",
        "SET_GATHER_RT",
        "CLEAR_GATHER_RT",
        "SET_VAR_LIGHTS",
        "SET_FOG_MAP",
        "RENDER_GATHER",

        "UPDATE_LUT",
        
        "SET_POST_PROCESS_DEPTH_STENCIL",
        # Internal Len reflection
        # Create downsampled threshold map
        "SET_VAR_POST_PROCESS_GATHER",
        "SET_ILR_THRESHOLD_RT",
        "SET_VAR_ILR_KERNEL_THRESHOLD",
        "RENDER_ILR_THRESHOLD",

        #   Blur the threshold map a couple of times
        "SET_VAR_ILR_THRESHOLD_0",
        "SET_VAR_ILR_KERNEL_0",
        "SET_ILR_BLOOM_RT_0",
        "RENDER_ILR_BLOOM_0",    
        "SET_VAR_ILR_THRESHOLD_1",
        "SET_VAR_ILR_KERNEL_1",
        "SET_ILR_BLOOM_RT_1",
        "RENDER_ILR_BLOOM_1",    

        # Merge the blooms into a single image
        "SET_VAR_ILR_MERGE_BLOOM0",
        "SET_VAR_ILR_MERGE_BLOOM1",
        "SET_VAR_ILR_MERGE_BLOOM2",
        "SET_ILR_MERGE_RT",
        "RENDER_ILR_MERGE",    

        # Composite bloom with final image
        "SET_POST_PROCESS_COMPOSITE_RT",
        "SET_VAR_ILR_BLOOM",
        "SET_VAR_ILR_REFLECTIONS_0",
        "SET_VAR_ILR_REFLECTIONS_1",
        "SET_VAR_ILR_TINT_0",
        "SET_VAR_ILR_TINT_1",
        "POST_PROCESS",


        "RENDER_FLARES",
        "END_MANAGED_RENDERING",
        "RESTORE_DEPTH_STENCIL_FOR_TOOLS",
        "UPDATE_TOOLS", 
        "RENDER_INFO",
        "RENDER_PROXY",
        "RENDER_VISUAL",
        "RENDER_TOOLS",             # Before the depth restore, if needed
        "RENDER_KYNAPSE",
        "RESTORE_DEPTH",
        "RENDER_UI",
        
        "PRESENT_SWAPCHAIN",
    ]

    # This structure describes how to create a double or quad-view version of this
    # The format is (keyName, sharedSetupStep=True/False, [stepkeys,...])
    # It is to be understood that the per-section data
    multiViewStages = [
        ("SETUP", True,
            [
                "UPDATE_SCENE",
                "UPDATE_BACKGROUND_SCENE",
                "SET_DEPTH",
                "BEGIN_MANAGED_RENDERING",
            ]),
        ("SETUP_BACKGROUND_RENDERING", True,
            [
                "SET_GATHER_RT",
                "CLEAR_BACKGROUND_RT",
            ]),
        ("SETUP_VIEW", False,
            [
                "SET_VIEWPORT",
                "SET_PROJECTION",
                "SET_VIEW",
                "VISIBILITY_QUERY", 
                "FILTER_VISIBILITY_RESULT", 
            ]),
        ("RENDER_BACKGROUNDS", False,
            [
                "SET_VIEWPORT",
                "UPDATE_BACKGROUND_CAMERA",
                "SET_BACKGROUND_PROJECTION",
                "SET_BACKGROUND_VIEW",
                "RENDER_BACKGROUND_SCENE",
            ]),
        ("RESTORE_FROM_BACKGROUND_RENDERING", True,
            [
                "CLEAR_BACKGROUND_DEPTH",
            ]),
        ("SETUP_PREPASS_PASS", True,
            [
                "SET_PREPASS_RT",
                "CLEAR_PREPASS",
            ]),
        ("PREPASS", False,
            [
                "SET_VIEWPORT",
                "SET_VIEW",
                "SET_PROJECTION",
                "SET_VISIBILITY_RESULT", 
                "SET_VISUALIZATION", # Visualizations are per-view                
                "ENABLE_WIREFRAME",
                "RENDER_PREPASS",
                "RESTORE_WIREFRAME",
            ]),
        ("SETUP_LIGHT_PASS", True,
            [
                "SET_LIGHT_RT",
                "CLEAR_LIGHTS",
                "SET_VAR_LIGHT_LUT",
                "SET_VAR_LIGHT_FRESNEL",
                "SET_VAR_LIGHTS_DEPTH",
                "SET_VAR_LIGHTS_PREPASS",
            ]),
        ("LIGHT_PASS", False,
            [
                "SET_VIEWPORT",
                "SET_VIEW",
                "SET_PROJECTION",
                "SET_VISIBILITY_RESULT", 
                "SET_VISUALIZATION", # Visualizations are per-view
                "RENDER_LIGHTS",
            ]),
        ("SETUP_GATHER", True,
            [
                "RENDER_SSAO",
                "SET_VAR_SSAO",
                "SET_GATHER_RT",
                "SET_VAR_LIGHTS",
            ]),
        ("GATHER_PASS", False,
            [
                "SET_VIEWPORT",
                "SET_VIEW",
                "SET_PROJECTION",
                "SET_VISIBILITY_RESULT", 
                "SET_VISUALIZATION", # Visualizations are per-view                
                "ENABLE_WIREFRAME",
                "DISABLE_CUBEMAP",
                "SET_FOG_MAP",
                "RENDER_GATHER",
                "ENABLE_CUBEMAP",
                "RESTORE_WIREFRAME",
                "RENDER_FLARES",
            ]),
        ("END_MANAGED_RENDERING", True,
            [ 
                "END_MANAGED_RENDERING",
            ]),
        ("TOOLS", False,
            [
                "SET_VIEWPORT",
                "SET_VIEW",
                "SET_PROJECTION",
                "UPDATE_TOOLS", 
                "RENDER_INFO",
                "RENDER_PROXY",
                "RENDER_VISUAL",
                "RENDER_TOOLS",
                "RENDER_KYNAPSE",
            ]),
        ("TEARDOWN", True,
            [
                "RESTORE_DEPTH",
            ])
    ]

    # List of classes that know how to modify this renderjob to apply visualizations
    visualizations = []
    
    def _ManualInit(self, name="EveSceneRenderJobInterior"):
        """
        Decorated classes cannot use a normal init function, so this must be called manually
        This version is called from ManualInit on SceneRenderJobBase
        """

        # This starts off un-chosen
        self.depthFormat = None
        self.prePassFormat = None
        self.lightAccumulationFormat = None
        
        # Store the rendertargets
        self.backBufferDepthStencil = None
        self.backBufferRenderTarget = None
        self.prePassDepthStencil = None
        self.prePassRenderTarget = None
        self.lightAccumulationTarget = None

        self.renderTargetCount = {}

        self.gatherTarget = None
        self.ilrMergeTarget = None # 1/4 Size
        self.ilrBloomTarget0 = None # 1/4 Size
        self.ilrBloomTarget1 = None # 1/8 Size
        self.ilrBloomTarget2 = None # 1/16 Size
        self.ilrBloomFormat = None
        
        self.ssaoTarget = None

        self.renderTargetList = None
                
        # in general most of these use weakrefs to prevent circular references
        self.ui = None

        self.backgroundScene = None
        self.backgroundUpdateFunction = None
        
        self.numShadowUpdates = 2

        self.ilrThresholdShader = None
        self.ilrBloomShader = None
        self.ilrMergeShader = None

        self.ilrEnabled = True
        self.lutEnabled = False
        self.noiseEnabled = False
        self.fxaaEnabled = False
        self.fxaaQuality = "FXAA_Low"

        self.ssaoEnabled = False

        self.postProcessShader = trinity.Tr2ShaderMaterial()
        self.postProcessShader.highLevelShaderName = "PostProcess"
        self.postProcessingParameters = {}

        self.fogTexturePath = ''

        self.previousLUTMap = None
        self.nextLUTMap = None
        self.lutBlend = 0
        self.lutTransitions = None
        self.lutPreviousTime = 0L

        self.noiseAmounts = (0.0, 0.0, 0.0, 1.0)
        
        self.lightingLUT = None
        self.fresnelLUT = None

        trinity.AddMipLevelSkipExclusionDirectory('res:/graphics/shared_texture/global/prepasslightlookup')

        self.SetSettingsBasedOnPerformancePreferences()
        
        self.ChooseBufferFormats()
        
    def Enable(self):
        SceneRenderJobBase.Enable(self)
        self.SetSettingsBasedOnPerformancePreferences()

    def SetSettingsBasedOnPerformancePreferences(self):
        """
        TODO: For now the settings are merged into a single performance setting, but these should be split and
        set in a group by the settings window
        """

        # TODO: Removing this line will break lighting in Jessica
        # Figure it out and fix it!
        if not self.enabled:
            return

        deviceSvc = sm.GetService("device")
        shadowQuality = gfxsettings.Get(gfxsettings.GFX_SHADOW_QUALITY)
        postProcessing = gfxsettings.Get(gfxsettings.GFX_POST_PROCESSING_QUALITY)
        self.fxaaEnabled = gfxsettings.Get(gfxsettings.GFX_ANTI_ALIASING) > 0
        self.fxaaQuality = self._GetFXAAQuality(gfxsettings.Get(gfxsettings.GFX_ANTI_ALIASING))
        self.numShadowUpdates = shadowQuality
        if shadowQuality != 0:
            self.numShadowUpdates = 4

        enableSSAO = deviceSvc.GetAppFeatureState("Interior.ssaoEnbaled", True)
        self.EnableSSAO( enableSSAO )

        if postProcessing == 0:
            # Low
            self.EnableLUT( False )
            self.EnableILR( False )
            self.EnableNoise( False )
        
        elif postProcessing == 1:
            # Medium
            self.EnableLUT( False )
            self.EnableILR( False )
            self.EnableNoise( False )

        else:
            # High
            self.EnableLUT( True )
            self.EnableILR( True )
            self.EnableNoise( True )

        self.EnableFXAA(self.fxaaEnabled, self.fxaaQuality)
        self.ApplyPerformancePreferencesToScene()

    def ApplyPerformancePreferencesToScene( self ):
        """
        Some performance options are per-scene (like shadow updates per frame).
        Apply them to the scene here.
        """
        currentScene = self.GetScene()

        if currentScene is not None:
            currentScene.shadowUpdatesPerFrame = self.numShadowUpdates
            currentScene.enableSHSolver = trinity.HasGlobalSituationFlag("OPT_INTERIOR_SM_HIGH")

    def _GetFXAAQuality(self, quality):
        if quality == 3:
            return "FXAA_High"
        elif quality == 2:
            return "FXAA_Medium"
        elif quality == 1:
            return "FXAA_Low"

        return ""

    def _GetRenderTargetIndex(self, format, width, height):
        key = (format, width, height)
        count = self.renderTargetCount.get(key, 0)
        self.renderTargetCount[key] = count + 1
        return count

    def _SetScene(self, scene):
        """
        Sets a scene into the render job
        """
        
        if hasattr(scene, 'id'):
            path = 'res:/Graphics/PostProcess/%i_postprocess.yaml' % scene.id
            self._LoadPostprocessingParameters(path, scene, False)
        elif scene is not None:
            self._ApplyDefaultPostprocessingParameters(scene)

        self.ApplyPerformancePreferencesToScene()
        
        if hasattr(scene, "enableROIs"):
            scene.enableROIs = False

        if scene is None:
            visibility = self.GetStep("VISIBILITY_QUERY")
            if visibility is not None and hasattr(visibility, 'results'):
                visibility.results.Clear()

        self.SetStepAttr("UPDATE_SCENE", 'object', scene)
        self.SetStepAttr("VISIBILITY_QUERY", 'queryable', scene)
        self.SetStepAttr("SET_VISIBILITY_RESULT", 'queryable', scene)
        self.SetStepAttr("BEGIN_MANAGED_RENDERING", 'scene', scene)
        self.SetStepAttr("RENDER_PREPASS", 'scene', scene)
        self.SetStepAttr("RENDER_LIGHTS", 'scene', scene)
        self.SetStepAttr("RENDER_GATHER", 'scene', scene)
        self.SetStepAttr("RENDER_FLARES", 'scene', scene)
        self.SetStepAttr("END_MANAGED_RENDERING", 'scene', scene)

    def ReloadPostprocessingParameters(self):
        """
        Reloads postprocessing parameters from per-worldspace configuration file.
        """
        scene = self.GetScene()

        if not scene:
            return None

        if hasattr(scene, 'id'):
            path = 'res:/Graphics/PostProcess/%i_postprocess.yaml' % scene.id
            self._LoadPostprocessingParameters(path, scene, True)
        else:
            self.postProcessingParameters = {}

    def _LoadPostprocessingParameters(self, path, scene, forceReload):
        """
        Loads postprocessing parameters from per-worldspace configuration file.
        """
        if blue.paths.exists(path):
            rf = blue.ResFile()
            rf.Open(path)
            yamlStr = rf.read()
            rf.close()

            data = yaml.load(yamlStr)

            self._ApplyPostprocessingParameters(data, scene, forceReload)
        else:
            self._ApplyDefaultPostprocessingParameters(scene)
        
    def _GetUpdateLUTCallback(self):
        """
        Returns a callback used by TriStepPythonCallback to update color LUT blend
        based on current camera position.
        """
        def UpdateLUT():
            """
            Updates color LUT blend based on current camera position.
            """
            if getattr(self.view, "object", None) is None or self.lutTransitions is None:
                return

            position = geo2.MatrixInverse(self.view.object.transform)[3]
            
            # Determine the closest transition plane
            closest = None
            closestDistance = 0
            for transition in self.lutTransitions:
                distance = geo2.Vec4Dot(position, transition['plane'])
                if closest is None or abs(distance) < abs(closestDistance):
                    closest = transition
                    closestDistance = distance
            transitionTime = 1
            # Switch LUT textures if needed
            if closest is not None:
                if closestDistance > 0:
                    map = closest['mapA']
                    transitionTime = closest['toSideATime']
                else:
                    map = closest['mapB']
                    transitionTime = closest['toSideBTime']
                if map != self.nextLUTMap:
                    if map == self.previousLUTMap:
                        temp = self.nextLUTMap
                        self.nextLUTMap = self.previousLUTMap
                        self.previousLUTMap = temp
                        self.lutBlend = 1 - self.lutBlend
                    elif self.previousLUTMap is None:
                        self.previousLUTMap = map
                        self.nextLUTMap = map
                        self.lutBlend = 0
                    else:
                        self.previousLUTMap = self.nextLUTMap
                        self.nextLUTMap = map
                        self.lutBlend = 0
                    self.SetLUTMaps(self.previousLUTMap, self.nextLUTMap)

            # Update blend value
            time = blue.os.GetWallclockTime()
            if self.lutPreviousTime == 0L:
                self.lutPreviousTime = time
            dt = min(blue.os.TimeDiffInMs(self.lutPreviousTime, time) / 1000.0, 0.1)
            self.lutPreviousTime = time
            
            self.lutBlend = min(self.lutBlend + dt / transitionTime, 1.0)
            self.SetLUTBlendAmount(self.lutBlend)

        return UpdateLUT
            
    
    def _ApplyPostprocessingParameters(self, data, scene, forceReload):
        """
        Applies postprocessing parameters from per-worldspace configuration file.
        """
        self.postProcessingParameters = data
        scene.minFogDistance = data['fog']['minFogDistance']
        scene.maxFogDistance = data['fog']['maxFogDistance']
        scene.maxFogAmount = data['fog']['maxFogAmount']
        if 'shScale' in data:
            scene.shScale = data['shScale']

        if 'environmentLighting' in data:
            scene.backgroundCubemapPath = data['environmentLighting']['cubeMap']

        self.fogTexturePath = data['fog']['texture']
        texture = blue.resMan.GetResource(self.fogTexturePath)
        if forceReload:
            texture.Reload()

        self.AddStep("SET_FOG_MAP", trinity.TriStepSetVariableStore("FogRampMap", texture))

        if not self.enabled or not self.canCreateRenderTargets:
            return
        
        self._RebuildPostProcess()

    def _ApplyDefaultPostprocessingParameters(self, scene):
        """
        Applies default postprocessing parameters for scenes that lack per-worldspace 
        configuration file or that are not worldspace scenes.
        """
        scene.maxFogAmount = 0
        scene.backgroundCubemapPath = ''
        self.fogTexturePath = ''
        self.AddStep("SET_FOG_MAP", trinity.TriStepSetVariableStore("FogRampMap", trinity.TriTextureRes()))
        self.EnableLUT(False)
        self.EnableNoise(False)

    def _CreateBasicRenderSteps(self):
        """
        This will clear the current steps. Create approximately the most basic renderjob setup.
        Assuming that someone wanted to use multiple versions of these together, then
        they would need to disable "CLEAR_PREPASS" and "CLEAR_LIGHTS", while sharing the
        render targets with the other steps
        """
        self.AddStep( "UPDATE_SCENE", trinity.TriStepUpdate( self.GetScene() ) )

        result = trinity.Tr2VisibilityResults()
        self.AddStep( "VISIBILITY_QUERY", trinity.TriStepVisibilityQuery( self.GetScene(), result ) )
        self.AddStep( "SET_VISIBILITY_RESULT", trinity.TriStepSetVisibilityResults( self.GetScene(), result ) )

        self.AddStep( "SET_PREPASS_RT",          trinity.TriStepSetRenderTarget() )
        self.AddStep( "CLEAR_PREPASS",           trinity.TriStepClear((0, 0, 0, 0), 1.0, 0))
        self.AddStep( "BEGIN_MANAGED_RENDERING", trinity.TriStepRenderPass(self.GetScene(), trinity.TRIPASS_BEGIN_RENDER))
        self.AddStep( "RENDER_PREPASS",          trinity.TriStepRenderPass(self.GetScene(), trinity.TRIPASS_PRE_PASS))
        self.AddStep( "SET_LIGHT_RT",            trinity.TriStepSetRenderTarget())

        # It is important not to clear the stencil and depth here
        self.AddStep("CLEAR_LIGHTS",            trinity.TriStepClear((0, 0, 0, 0), None, None))
               
        # Render the light accumulation pass
        self.AddStep("RENDER_LIGHTS", trinity.TriStepRenderPass(self.GetScene(), trinity.TRIPASS_LIGHT_PASS))
        
        # Switch back to the original render target
        if self.GetSwapChain() is None:
            self.AddStep( "SET_GATHER_RT", trinity.TriStepSetRenderTarget())
        else:
            self.AddStep( "SET_GATHER_RT", trinity.TriStepSetRenderTarget(self.GetSwapChain().backBuffer) )
        self.AddStep("CLEAR_GATHER_RT",  trinity.TriStepClear((0, 0, 0, 0), None, None))
        
        # Draw objects with materials
        self.AddStep("RENDER_GATHER", trinity.TriStepRenderPass(self.GetScene(), trinity.TRIPASS_GATHER_PASS))
        
        # Draw flares
        self.AddStep("RENDER_FLARES", trinity.TriStepRenderPass(self.GetScene(), trinity.TRIPASS_FLARE_PASS))
        
        # And finish managed rendering for this
        self.AddStep("END_MANAGED_RENDERING", trinity.TriStepRenderPass(self.GetScene(), trinity.TRIPASS_END_RENDER))

    def AddBloomStep(self, source, target, step, kernelWidth):

        self.AddStep("SET_VAR_ILR_THRESHOLD_%d" % step, trinity.TriStepSetVariableStore("BloomMap", source))
        self.AddStep("SET_VAR_ILR_KERNEL_%d" % step,    trinity.TriStepSetVariableStore("BloomWidth", (kernelWidth/source.width, kernelWidth/source.height )))
        self.AddStep("SET_ILR_BLOOM_RT_%d" % step,      trinity.TriStepSetRenderTarget(target))
        self.AddStep("RENDER_ILR_BLOOM_%d" % step,      trinity.TriStepRenderFullScreenShader(self.ilrBloomShader))

    def ChooseBufferFormats(self):
        """
        This function is called before the renderjob creates the render targets.
        This can happen within a device reset, which is too late for us to change shader models again (and not allowed)
        Therefore this function just chooses the only valid formats, given the currently selected option.
        If the option is invalid, there may be exceptions trying to create these render targets and depth stencil surfaces,
        which we would need to respond to.
        """
        # Pretty much everything supports this... can we reuse the existing one?
        self.depthFormat = None
        customDepthFormat = False

        # If we're on SM_3_0_HI and we support IntZ, we can upgrade to that
        if trinity.HasGlobalSituationFlag('OPT_INTZ'):
            self.depthFormat = trinity.DEPTH_STENCIL_FORMAT.READABLE
            self.prePassFormat = trinity.PIXEL_FORMAT.R16G16B16A16_UNORM
            self.lightAccumulationFormat = trinity.PIXEL_FORMAT.R16G16B16A16_FLOAT
            self.ilrBloomFormat = trinity.PIXEL_FORMAT.R16G16B16A16_FLOAT
            self.gatherFormat = trinity.PIXEL_FORMAT.R16G16B16A16_FLOAT

            customDepthFormat = True
        else:
            self.prePassFormat = trinity.PIXEL_FORMAT.R16G16B16A16_UNORM
            self.lightAccumulationFormat = trinity.PIXEL_FORMAT.R16G16B16A16_FLOAT
            self.ilrBloomFormat = trinity.PIXEL_FORMAT.R16G16B16A16_FLOAT
            self.gatherFormat = trinity.PIXEL_FORMAT.R16G16B16A16_FLOAT

        if not trinity.HasGlobalSituationFlag('OPT_INTERIOR_SM_HIGH'):
            self.lightAccumulationFormat = trinity.PIXEL_FORMAT.B8G8R8A8_UNORM
            self.gatherFormat = trinity.PIXEL_FORMAT.B8G8R8A8_UNORM
        
        # Don't need to set the buffers now
        if not customDepthFormat:
            self.RemoveStep("SET_DEPTH")
            self.RemoveStep("RESTORE_DEPTH")

    def DoReleaseResources(self, level):
        """
        This function is called when the device is lost.
        """
        # Release the render targets and stencil surfaces
        self.SetRenderTargets(None, 
                               None, 
                               None, 
                               None, 
                               None,
                               None,
                               None,
                               None,
                               None,
                               None,
                               None)
        self.renderTargetList = None
        self.backBufferDepthStencil = None
        self.gatherTarget = None
        self.backBufferRenderTarget = None
        self.prePassDepthStencil = None
        self.prePassRenderTarget = None
        self.lightAccumulationTarget = None       
        self.ilrMergeTarget = None
        self.ilrBloomTarget0 = None 
        self.ilrBloomTarget1 = None 
        self.ilrBloomTarget2 = None 
        self.ssaoTarget = None
        self.renderTargetCount = {}

    def InitializeShaders(self):
        self.ilrBloomShader = trinity.Tr2ShaderMaterial()
        self.ilrBloomShader.highLevelShaderName = "ILR_Bloom"
        self.ilrBloomShader.BindLowLevelShader(['none'])

        self.ilrThresholdShader = trinity.Tr2ShaderMaterial()
        self.ilrThresholdShader.highLevelShaderName = "ILR_Threshold"
        self.ilrThresholdShader.BindLowLevelShader(['none'])

        self.ilrMergeShader = trinity.Tr2ShaderMaterial()
        self.ilrMergeShader.highLevelShaderName = "ILR_Merge"
        self.ilrMergeShader.BindLowLevelShader(['none'])

    def DoPrepareResources(self):
        """
        This function is called when the device is restored. 
        This function may raise exceptions attempting to create resources!
        NB: Will need to be changed to allow other sources to provide the buffers
        """
                
        if not self.enabled or not self.canCreateRenderTargets:
            return
            
        if self.fogTexturePath != '':
            texture = blue.resMan.GetResource(self.fogTexturePath)
            self.AddStep("SET_FOG_MAP", trinity.TriStepSetVariableStore("FogRampMap", texture))

        self.lightingLUT = blue.resMan.GetResource("res:/Graphics/Shared_Texture/Global/prepassLightLookup.dds")
        self.fresnelLUT = blue.resMan.GetResource("res:/Graphics/Shared_Texture/Global/prepassLightLookupFresnel.dds")
        self.AddStep( "SET_VAR_LIGHT_LUT",       trinity.TriStepSetVariableStore("LightingLUT", self.lightingLUT))
        self.AddStep( "SET_VAR_LIGHT_FRESNEL",   trinity.TriStepSetVariableStore("FresnelLUT", self.fresnelLUT))

        # TODO: This check does not allow re-creation of resources with a single call
        # to this function.  Instead, you must call DoReleaseResources first.
        # This needs to be fixed.
        if self.renderTargetList is None: 
                
            # RT support & back buffer may have changed
            width, height = self.GetBackBufferSize()

            self.ChooseBufferFormats()
            
            if self.backBufferRenderTarget is None:
                self.backBufferRenderTarget = self.GetBackBufferRenderTarget()
            
            # This is what we will use for the pre-pass, which may or may not be the same as the back buffer
            if self.depthFormat is not None and self.prePassDepthStencil is None:
                self.prePassDepthStencil = self.GetDepthStencilWithRTMAL(self.depthFormat,
                    None,
                    self._GetRenderTargetIndex(self.depthFormat, width, height))
                
                try:
                    self.prePassDepthStencil.name = "sceneRenderJobInterior.prePassDepthStencil"
                except:
                    pass

            if self.prePassFormat is not None and self.prePassRenderTarget is None:
                self.prePassRenderTarget = rtm.GetRenderTargetAL(
                    width, height, 1, 
                    self.prePassFormat, 
                    index = self._GetRenderTargetIndex(self.prePassFormat, width, height))
                if self.prePassRenderTarget is not None:
                    self.prePassRenderTarget.name = 'sceneRenderJobInterior.prePassRenderTarget'
        
            if self.lightAccumulationFormat is not None and self.lightAccumulationTarget is None:
                self.lightAccumulationTarget = rtm.GetRenderTargetAL(
                    width, height, 1, 
                    self.lightAccumulationFormat, 
                    index = self._GetRenderTargetIndex(self.lightAccumulationFormat, width, height))
                if self.lightAccumulationTarget is not None:
                    self.lightAccumulationTarget.name = 'sceneRenderJobInterior.lightAccumulationTarget'

            self._RebuildPostProcess()
    
            if self.ssaoEnabled:
                self.ssaoTarget = self.CreateSSAORenderTarget()
            else:
                self.ssaoTarget = blue.resMan.GetResource('res:/Texture/Global/white.dds')
            
            self.renderTargetList = (
                                blue.BluePythonWeakRef(self.backBufferDepthStencil), 
                                blue.BluePythonWeakRef(self.backBufferRenderTarget), 
                                blue.BluePythonWeakRef(self.prePassDepthStencil),  
                                blue.BluePythonWeakRef(self.prePassRenderTarget), 
                                blue.BluePythonWeakRef(self.lightAccumulationTarget),
                                blue.BluePythonWeakRef(self.ilrBloomTarget0),
                                blue.BluePythonWeakRef(self.ilrBloomTarget1),
                                blue.BluePythonWeakRef(self.ilrBloomTarget2),
                                blue.BluePythonWeakRef(self.ilrMergeTarget),
                                blue.BluePythonWeakRef(self.gatherTarget),
                                blue.BluePythonWeakRef(self.ssaoTarget),
                                )
        

        thingToSet = (x.object for x in self.renderTargetList)
        self.SetRenderTargets(*thingToSet)

    def SetUI(self, ui):
        """
        This call adds or removes the steps nessecary for rendering the UI
        depending on if 'ui' is None
        """
        if ui is None:
            self.RemoveStep("UPDATE_UI")
            self.RemoveStep("RENDER_UI")
        else:
            self.AddStep("UPDATE_UI", trinity.TriStepUpdate(ui))
            self.AddStep("RENDER_UI", trinity.TriStepRenderUI(ui))

    def SetCameraView(self, view):
        SceneRenderJobBase.SetCameraView(self, view)
        self.UpdateBackgroundCameraCallbackWithNewForegroundCamera()

    def SetCameraProjection(self, proj):
        SceneRenderJobBase.SetCameraProjection(self, proj)
        self.UpdateBackgroundCameraCallbackWithNewForegroundCamera()

    def GetBackgroundUpdateCallbackFunction(self, foregroundView, foregroundProjection, f):
        """ 
        Given f, which takes a foregroundView and foregroundProjection, make a closure that's callable without any arguments.
        """
        def CameraUpdateCallbackClosure():
            return f(foregroundView, foregroundProjection)

        return CameraUpdateCallbackClosure

    def GetBackgroundCameraUpdateFunction(self, backgroundView, backgroundProjection, backgroundNearClip, backgroundFarClip, translation, rotation):
        """
        Return a function closure that will update the given background TriView and TriProjection matrices based on dynamic foreground matrices
        and the information given in this function
        """
        import geo2
        additionalViewTranform = geo2.MatrixTransformation(
                                    (0.0, 0.0, 0.0),        # Scaling center
                                    (0.0, 0.0, 0.0, 1.0),  # Scaling rotation
                                    (1.0, 1.0, 1.0),        # Scaling vector
                                    (0.0, 0.0, 0.0),        # Rotation center
                                    rotation,
                                    translation
                                    )

        def UpdateBackgroundCamera(foregroundView, foregroundProjection):
            """
            This function is a closure that contains the information passed into GetBackgroundCameraUpdateFunction
            It produces a function that should be used to generate another closure with the foreground view and projection
            set, so that the resulting function needs no arguments and can be called on a python callback step interleaved in the rendering.

            Another scheme for doing this, is to build the logic into the camera itself, but this involves changing a number of possible cameras
            so I'm avoiding doing it and providing a general, but slightly difficult to debug fallback.
            """
            foregroundViewInverted = geo2.MatrixInverse(foregroundView.transform)
            backgroundViewInverted = geo2.MatrixMultiply(foregroundViewInverted, additionalViewTranform)

            # Update the TriView for the background
            backgroundView.transform = geo2.MatrixInverse(backgroundViewInverted)

            originalProjection = foregroundProjection.transform

            # Check if it's a right handed perspective projection
            if originalProjection[3][3] == 0:
                # Assume that this is a perspective projection
                # Assume right handed
                # Please see: http://msdn.microsoft.com/en-us/library/bb205355%28v=VS.85%29.aspx

                # We only need to change the front and back clip properties of the projection
                # m_33 = z_f/(z_f-z_n)
                # m_43 = -z_n*z_f/(z_f-z_n)
                new33 = backgroundFarClip / (backgroundNearClip - backgroundFarClip)
                new43 = (backgroundNearClip * backgroundFarClip) / (backgroundNearClip - backgroundFarClip)

                newProjectionTransform = (
                        originalProjection[0],
                        originalProjection[1],
                        (originalProjection[2][0], originalProjection[2][1], new33, originalProjection[2][3] ),
                        (originalProjection[3][0], originalProjection[3][1], new43, originalProjection[3][3] )
                    )

                backgroundProjection.CustomProjection(newProjectionTransform)

            else:
                # Assume that this is an orthographic projection
                # Please see: http://msdn.microsoft.com/en-us/library/bb205349%28v=vs.85%29.aspx
                # m_33 = 1/(zn-zf) 
                # m_43 = zn/(zn-zf)

                new33 = 1.0 / (backgroundNearClip - backgroundFarClip)
                new43 = backgroundNearClip / (backgroundNearClip - backgroundFarClip)

                newProjectionTransform = (
                        originalProjection[0],
                        originalProjection[1],
                        (originalProjection[2][0], originalProjection[2][1], new33, originalProjection[2][3] ),
                        (originalProjection[3][0], originalProjection[3][1], new43, originalProjection[3][3] )
                    )
                
                backgroundProjection.CustomProjection(newProjectionTransform)
        return UpdateBackgroundCamera


    def SetBackgroundCameraViewAndProjection(self, view, projection, updateFunction):
        """
        This call sets up a camera with which a background scene could be rendered
        """
        self.backgroundUpdateFunction = None

        if view is None or projection is None:
            self.RemoveStep("SET_BACKGROUND_PROJECTION" )
            self.RemoveStep("SET_BACKGROUND_VIEW" )
            self.RemoveStep("UPDATE_BACKGROUND_CAMERA" )
        else:
            self.AddStep("SET_BACKGROUND_VIEW", trinity.TriStepSetView(view))
            self.AddStep("SET_BACKGROUND_PROJECTION", trinity.TriStepSetProjection(projection))

            self.backgroundUpdateFunction = updateFunction
            self.UpdateBackgroundCameraCallbackWithNewForegroundCamera()

    def UpdateBackgroundCameraCallbackWithNewForegroundCamera(self):
        """
        Given a self.backgroundUpdateFunction that takes a TriView and TriProjection from the main camera
        create a callback function with no arguments, and set it to the "UPDATE_BACKGROUND_CAMERA" step
        """
        if self.view is not None:
            originalView = self.view.object
            if originalView is None:
                return
        else:
            return       

        if self.projection is not None:
            originalProjection = self.projection.object
            if originalProjection is None:
                return
        else:
            return

        if self.backgroundUpdateFunction is None:
            return

        if originalProjection is not None and originalView is not None:
            callback = self.GetBackgroundUpdateCallbackFunction(originalView, originalProjection, self.backgroundUpdateFunction)

            upd = self.AddStep("UPDATE_BACKGROUND_CAMERA", trinity.TriStepPythonCB())
            if upd is not None:
                upd.SetCallback(callback)
                return True

    def SetBackgroundScene(self, scene):
        """
        This call sets up a background scene (forwards rendered) that is drawn instead of
        the environment map.
        """
        if scene is None:
            self.RemoveStep("UPDATE_BACKGROUND_SCENE")
            self.RemoveStep("RENDER_BACKGROUND_SCENE")

            # Just clear the colour of the final render target
            self.AddStep("CLEAR_GATHER_RT",  trinity.TriStepClear((0, 0, 0, 0), None, None))

            # Make sure we don't have this clear, because the background RT won't be set
            self.RemoveStep("CLEAR_BACKGROUND_RT" )
            self.RemoveStep("CLEAR_BACKGROUND_DEPTH" )

            self.RemoveStep("SET_BACKGROUND_RT")

            self.backgroundScene = None

        else:
            self.AddStep("UPDATE_BACKGROUND_SCENE", trinity.TriStepUpdate(scene))
            self.AddStep("RENDER_BACKGROUND_SCENE", trinity.TriStepRenderScene(scene))

            # In this case, this is the initial clear, so clear everything
            # Prepass clear will wipe this out again
            self.AddStep("CLEAR_BACKGROUND_RT",  trinity.TriStepClear((0, 0, 0, 0), 1.0, 0))

            # Clear the depth and stencil after rendering the background
            self.AddStep("CLEAR_BACKGROUND_DEPTH", trinity.TriStepClear(None, 1.0, 0))


            # We don't clear the final render target if we're rendering a background scene before it
            self.RemoveStep("CLEAR_GATHER_RT")
            
            if self.gatherTarget is not None:
                self.AddStep("SET_BACKGROUND_RT", trinity.TriStepSetRenderTarget(self.gatherTarget))

            self.backgroundScene = blue.BluePythonWeakRef(scene)

    def SuspendRendering(self):
        self.Pause()

    def EnableSceneUpdate(self, isEnabled):
        if isEnabled:
            self.AddStep("UPDATE_SCENE", trinity.TriStepUpdate(self.GetScene()))
        else:
            self.RemoveStep("UPDATE_SCENE")

    def EnableVisibilityQuery(self, isEnabled):        
        """
        Enables or disables the visibility query 
        """
        if isEnabled:
            result = trinity.Tr2VisibilityResults()
            self.AddStep("VISIBILITY_QUERY", trinity.TriStepVisibilityQuery(self.GetScene(), result))
            self.AddStep("SET_VISIBILITY_RESULT", trinity.TriStepSetVisibilityResults(self.GetScene(), result))
        else:
            self.RemoveStep("VISIBILITY_QUERY")
            self.RemoveStep("SET_VISIBILITY_RESULT")

    def EnableBackBufferClears(self, isEnabled):
        if isEnabled:
            self.AddStep("CLEAR_PREPASS", trinity.TriStepClear((0, 0, 0, 0), 1.0, 0))
            self.AddStep("CLEAR_LIGHTS",  trinity.TriStepClear((0, 0, 0, 0), None, None))
        else:
            self.RemoveStep("CLEAR_PREPASS")
            self.RemoveStep("CLEAR_LIGHTS")
               
    
    def CreateSSAORenderTarget(self):
        """
        Returns a new render target for SSAO.
        """
        width, height = self.GetBackBufferSize()
        
        ssaoFormat = trinity.PIXEL_FORMAT.B5G6R5_UNORM
        target = rtm.GetRenderTargetAL(
            width, height, 1, 
            ssaoFormat, 
            index = self._GetRenderTargetIndex(ssaoFormat, width, height))
        if not target.IsValid():
            ssaoFormat = trinity.PIXEL_FORMAT.B8G8R8A8_UNORM
            target = rtm.GetRenderTargetAL(
                width, height, 1, 
                ssaoFormat, 
                index = self._GetRenderTargetIndex(ssaoFormat, width, height))
        if target is not None:
            target.name = 'sceneRenderJobInterior.SSAO'
        return target

    def EnableSSAO(self, enable):
        """
        Enables/disables SSAO.
        """
        self.ssaoEnabled = enable
        if enable:
            options = renderSSAOJob.SSAOOptions()
            
            rf = blue.ResFile()
            try:
                rf.Open('res://Graphics/postprocess/SSAO.yaml')
                yamlStr = rf.read()
                rf.close()

                data = yaml.load(yamlStr)
                for member in data:
                    if member in options.__class__.__dict__:
                        options.__dict__[member] = data[member]
            except:
                pass
            
            self.ssaoTarget = self.CreateSSAORenderTarget()
            if self.ssaoTarget.IsValid():
                rj = renderSSAOJob.CreateSsaoRenderJob(options, self.ssaoTarget.width, self.ssaoTarget.height, self.ssaoTarget)
                if rj is not None:
                    self.AddStep("RENDER_SSAO", trinity.TriStepRunJob(rj))
                    self.AddStep("SET_VAR_SSAO", trinity.TriStepSetVariableStore("SSAOMap", self.ssaoTarget))
                return
                
        self.ssaoTarget = blue.resMan.GetResource('res:/Texture/Global/white.dds')
        self.AddStep("SET_VAR_SSAO", trinity.TriStepSetVariableStore("SSAOMap", self.ssaoTarget))
        self.RemoveStep("RENDER_SSAO")

    def LoadILRSettings(self):
        import yaml

        scene = self.GetScene()

        if not scene:
            return None

        if hasattr(scene, 'id'):
            resPath = r"res:\Graphics\PostProcess\ILR_%s.yaml" % scene.id
            if resPath is None:
                return
        else:
            return

        if blue.paths.exists(resPath):
            rf = blue.ResFile()
            rf.Open(resPath)
            yamlStr = rf.read()
            rf.close()

            ilrValues = yaml.load(yamlStr)

            ref0 = (
                ilrValues.get("Reflection0", 1),
                ilrValues.get("Reflection1", 1),
                ilrValues.get("Reflection2", 1),
                ilrValues.get("Reflection3", 1),
                )

            ref1 = (
                ilrValues.get("Reflection4", 1),
                ilrValues.get("Reflection5", 1),
                ilrValues.get("Reflection6", 1),
                ilrValues.get("Intensity", 1),
                )

            tint0 = (
                ilrValues.get("TintR_Center", 1),
                ilrValues.get("TintG_Center", 1),
                ilrValues.get("TintB_Center", 1),
                1.0,
                )

            tint1 = (
                ilrValues.get("TintR_Edge", 1),
                ilrValues.get("TintG_Edge", 1),
                ilrValues.get("TintB_Edge", 1),
                1.0,
                )

            width = ilrValues.get("BloomWidth", 1)

            self.SetReflections(ref0, ref1)
            self.SetTints(tint0, tint1)
            self.SetBlurKernel(width)

    def SetReflections(self, ref0, ref1):
        self.AddStep("SET_VAR_ILR_REFLECTIONS_0" , trinity.TriStepSetVariableStore("BloomReflections0", ref0))
        self.AddStep("SET_VAR_ILR_REFLECTIONS_1" , trinity.TriStepSetVariableStore("BloomReflections1", ref1))

    def SetTints(self, tint0, tint1):
        self.AddStep("SET_VAR_ILR_TINT_0" , trinity.TriStepSetVariableStore("BloomTint0", tint0))
        self.AddStep("SET_VAR_ILR_TINT_1" , trinity.TriStepSetVariableStore("BloomTint1", tint1))

    def SetBlurKernel(self, width=1.5):
        self.AddBloomStep(self.ilrBloomTarget0, self.ilrBloomTarget1, 0, width)
        self.AddBloomStep(self.ilrBloomTarget1, self.ilrBloomTarget2, 1, width*2)

    def SetLUTMaps(self, LUTMap0, LUTMap1):
        """
        Sets LUT texture maps.
        """
        if LUTMap0 is None:
            self.postProcessShader['LUTMap0'] = None
        else:
            rebind = False
            if 'LUTMap0' not in self.postProcessShader.parameters:
                param = trinity.TriTextureParameter()
                param.name = 'LUTMap0'
                self.postProcessShader.parameters['LUTMap0'] = param
                rebind = True
            self.postProcessShader.parameters['LUTMap0'].SetResource(LUTMap0)
            if 'LUTMap1' not in self.postProcessShader.parameters:
                param = trinity.TriTextureParameter()
                param.name = 'LUTMap1'
                self.postProcessShader.parameters['LUTMap1'] = param
                rebind = True
            self.postProcessShader.parameters['LUTMap1'].SetResource(LUTMap1)
            if rebind:
                self.postProcessShader.BindLowLevelShader([])

    def SetLUTBlendAmount(self, lutBlend):
        """
        Sets blend abount (from 0 to 1) between color LUT textures.
        """
        if 'LUTBlendAmount' not in self.postProcessShader.parameters:
            param = trinity.Tr2FloatParameter()
            param.name = 'LUTBlendAmount'
            self.postProcessShader.parameters['LUTBlendAmount'] = param
            self.postProcessShader.BindLowLevelShader([])
        self.postProcessShader.parameters['LUTBlendAmount'].value = lutBlend

    def SetLUTInfluence(self, LUTInfluence):
        """
        Sets LUT correction coefficient (0 to 1).
        """
        self.LUTInfluence = LUTInfluence
        if 'LUTInfluence' not in self.postProcessShader.parameters:
            param = trinity.Tr2FloatParameter()
            param.name = 'LUTInfluence'
            self.postProcessShader.parameters['LUTInfluence'] = param
            self.postProcessShader.BindLowLevelShader([])
        self.postProcessShader.parameters['LUTInfluence'].value = LUTInfluence

    def EnableLUT(self, enable):
        """
        Enables or disables LUT correction.
        """
        self.lutEnabled = enable
        if self.enabled and self.renderTargetList is not None:
            self._RebuildPostProcess()

    def EnableFXAA(self, enable, mode="FXAA_Medium"):
        """
        Enables or disables FXAA.
        """
        self.fxaaEnabled = enable
        self.fxaaQuality = mode
        if self.enabled and self.renderTargetList is not None:
            self._RebuildPostProcess()

    def HasPostProcess(self):
        """
        Returns True iff the render job has post processing enabled.
        """
        return self.fxaaEnabled or self.lutEnabled or self.ilrEnabled or self.noiseEnabled

    def EnableILR(self, isEnabled):
        """
        Enables or disables Internal Lens Reflection
        """

        self.ilrEnabled = isEnabled
        
        if self.enabled and self.renderTargetList is not None:
            self._RebuildPostProcess()

    def EnableNoise(self, isEnabled):
        """
        Enables or disables noise post-processing.
        """
        self.noiseEnabled = isEnabled
        if self.enabled and self.renderTargetList is not None:
            self._RebuildPostProcess()

    def _RebuildPostProcess(self):
        """
        Rebuilds postprocessing resources: render targets, shaders, render steps.
        """
        BLOOM_BUFFER_SCALE_0 = 4
        BLOOM_BUFFER_SCALE_1 = 4
        BLOOM_BUFFER_SCALE_2 = 8

        width, height = self.GetBackBufferSize()

        # Disable ILR on ATI cards with Windows XP: drivers don't
        # handle ILR correctly. Do it here instead of in EnableILR
        # because EnableILR could theoretically be called before
        # the device is created.
        if not blue.win32.IsTransgaming():
            try:
                info = _singletons.adapters.GetAdapterInfo(_singletons.device.adapter)
                if info.vendorID == 4098 and blue.os.osMajor <= 5:
                    self.ilrEnabled = False
            except:
                pass

        if self.HasPostProcess():
            if self.AddStep("POST_PROCESS", trinity.TriStepRenderFullScreenShader(self.postProcessShader)) is None:
                return

            if self.gatherTarget is None:
                self.gatherTarget = rtm.GetRenderTargetAL(
                    width, height, 1, 
                    self.gatherFormat,
                    self._GetRenderTargetIndex(self.gatherFormat, width, height))
                if self.gatherTarget is not None:
                    self.gatherTarget.name = 'sceneRenderJobInterior.gatherTarget'

            trinity.GetVariableStore().RegisterVariable("GatherMap", self.gatherTarget)
            
            if self.ilrEnabled:
                if self.ilrBloomFormat is not None and self.ilrBloomTarget0 is None:
                    index = self._GetRenderTargetIndex(
                        self.ilrBloomFormat, 
                        width/BLOOM_BUFFER_SCALE_0, 
                        height/BLOOM_BUFFER_SCALE_0)

                    self.ilrBloomTarget0 = rtm.GetRenderTargetAL(
                        width/BLOOM_BUFFER_SCALE_0, height/BLOOM_BUFFER_SCALE_0, 1,
                        self.ilrBloomFormat,
                        index=index)

                    index = self._GetRenderTargetIndex(
                        self.ilrBloomFormat, 
                        width/BLOOM_BUFFER_SCALE_1, 
                        height/BLOOM_BUFFER_SCALE_1)

                    self.ilrBloomTarget1 = rtm.GetRenderTargetAL(
                        width/BLOOM_BUFFER_SCALE_1, height/BLOOM_BUFFER_SCALE_1, 1,
                        self.ilrBloomFormat,
                        index=index)

                    
                    index = self._GetRenderTargetIndex(
                        self.ilrBloomFormat, 
                        width/BLOOM_BUFFER_SCALE_2, 
                        height/BLOOM_BUFFER_SCALE_2)

                    self.ilrBloomTarget2 = rtm.GetRenderTargetAL(
                        width/BLOOM_BUFFER_SCALE_2, height/BLOOM_BUFFER_SCALE_2, 1,
                        self.ilrBloomFormat,
                        index=index)
                    
                    index = self._GetRenderTargetIndex(
                        self.ilrBloomFormat, 
                        width/BLOOM_BUFFER_SCALE_0, 
                        height/BLOOM_BUFFER_SCALE_0)

                    self.ilrMergeTarget = rtm.GetRenderTargetAL(
                        width/BLOOM_BUFFER_SCALE_0, height/BLOOM_BUFFER_SCALE_0, 1,
                        self.ilrBloomFormat,
                        index=index)
                        
                    if self.ilrBloomTarget0 is not None:
                        self.ilrBloomTarget0.name = 'sceneRenderJobInterior.ilrBloomTarget0'
                    if self.ilrBloomTarget1 is not None:
                        self.ilrBloomTarget1.name = 'sceneRenderJobInterior.ilrBloomTarget1'
                    if self.ilrBloomTarget2 is not None:
                        self.ilrBloomTarget2.name = 'sceneRenderJobInterior.ilrBloomTarget2'
                    if self.ilrMergeTarget is not None:
                        self.ilrMergeTarget.name = 'sceneRenderJobInterior.ilrMergeTarget'

            self.InitializeShaders()

            if self.ilrEnabled:
                self.AddStep("RENDER_ILR_THRESHOLD", trinity.TriStepRenderFullScreenShader(self.ilrThresholdShader))

                self.SetReflections((-0.6, -0.5, -0.15, -0.3),
                                    (1.4, 1.8, -1.5, 1))

                self.AddStep("SET_VAR_ILR_MERGE_BLOOM0", trinity.TriStepSetVariableStore("BloomMap",  self.ilrBloomTarget0))
                self.AddStep("SET_VAR_ILR_MERGE_BLOOM1", trinity.TriStepSetVariableStore("BloomMap1", self.ilrBloomTarget1))
                self.AddStep("SET_VAR_ILR_MERGE_BLOOM2", trinity.TriStepSetVariableStore("BloomMap2", self.ilrBloomTarget2))
                self.AddStep("SET_ILR_MERGE_RT", trinity.TriStepSetRenderTarget(self.ilrMergeTarget))
                self.AddStep("RENDER_ILR_MERGE",  trinity.TriStepRenderFullScreenShader(self.ilrMergeShader))  

                self.SetBlurKernel()

                trinity.GetVariableStore().RegisterVariable("BloomMap", self.ilrBloomTarget0)
                trinity.GetVariableStore().RegisterVariable("BloomMap1", self.ilrBloomTarget0)
                trinity.GetVariableStore().RegisterVariable("BloomMap2", self.ilrBloomTarget0)
                trinity.GetVariableStore().RegisterVariable("BloomWidth", (0.0, 0.0))
                trinity.GetVariableStore().RegisterVariable("BloomReflections0", (0.0, 0.0, 0.0, 0.0))
                trinity.GetVariableStore().RegisterVariable("BloomReflections1", (0.0, 0.0, 0.0, 0.0))
                trinity.GetVariableStore().RegisterVariable("BloomTint0", (0.0, 0.0, 0.0, 0.0))
                trinity.GetVariableStore().RegisterVariable("BloomTint1", (0.0, 0.0, 0.0, 0.0))

                self.ilrBloomShader.BindLowLevelShader(['none'])
                self.ilrThresholdShader.BindLowLevelShader(['none'])
                self.ilrMergeShader.BindLowLevelShader(['none'])
            else:
                self.ilrBloomTarget0 = None
                self.ilrBloomTarget1 = None
                self.ilrBloomTarget2 = None
                self.ilrMergeTarget = None
                self._ClearILRSteps()

            self.postProcessShader.defaultSituation = ''
            if self.ilrEnabled:
                self.postProcessShader.defaultSituation = 'ILR'
            if self.lutEnabled:
                if 'lut' in self.postProcessingParameters:
                    self.lutTransitions = self.postProcessingParameters['lut']['transitions']
                    for transition in self.lutTransitions:
                        transition['plane'] = (transition['normal'][0], transition['normal'][1], transition['normal'][2], -geo2.Vec3Dot(transition['point'], transition['normal']))
                        transition['mapA'] = blue.resMan.GetResource(transition['sideA'])
                        transition['mapB'] = blue.resMan.GetResource(transition['sideB'])
                    update = self.AddStep("UPDATE_LUT", trinity.TriStepPythonCB())
                    # If update is None we are probably in Multiview
                    if update is not None:
                        update.SetCallback(self._GetUpdateLUTCallback())
                        self.SetLUTInfluence(self.postProcessingParameters['lut']['influence'])
                    self.postProcessShader.defaultSituation += ' LUT'
            else:
                self.RemoveStep("UPDATE_LUT")
            if self.noiseEnabled:
                if 'noise' in self.postProcessingParameters:
                    self.noiseAmounts = (self.postProcessingParameters['noise']['darkAmount'], self.postProcessingParameters['noise']['darkIntensity'], self.postProcessingParameters['noise']['brightAmount'], self.postProcessingParameters['noise']['brightIntensity'])

                    self.postProcessShader.defaultSituation += ' Noise'

                noise = trinity.TriTextureParameter()
                noise.name = 'NoiseMap'
                noise.resourcePath = 'res:/Texture/Global/noise.dds'
                self.postProcessShader.parameters['NoiseMap'] = noise
                
                noiseAmount = trinity.Tr2Vector4Parameter()
                noiseAmount.name = 'NoiseAmount'
                noiseAmount.value = self.noiseAmounts
                self.postProcessShader.parameters['NoiseAmount'] = noiseAmount
            if self.fxaaEnabled:
                self.postProcessShader.defaultSituation += ' ' + self.fxaaQuality
            
            self.postProcessShader.BindLowLevelShader([])

            self.SetStepAttr("SET_GATHER_RT", 'renderTarget', self.gatherTarget)
            self.AddStep("SET_VAR_POST_PROCESS_GATHER", trinity.TriStepSetVariableStore("GatherMap", self.gatherTarget))
            self.AddStep("SET_POST_PROCESS_DEPTH_STENCIL", trinity.TriStepPushDepthStencil(None))
            self.AddStep("RESTORE_DEPTH_STENCIL_FOR_TOOLS", trinity.TriStepPopDepthStencil())
            self.AddStep("SET_POST_PROCESS_COMPOSITE_RT", trinity.TriStepSetRenderTarget(self.backBufferRenderTarget))

            if self.backgroundScene is not None:
                self.AddStep("SET_BACKGROUND_RT", trinity.TriStepSetRenderTarget(self.gatherTarget))

            if self.ilrEnabled:
                self.AddStep("SET_ILR_THRESHOLD_RT", trinity.TriStepSetRenderTarget(self.ilrBloomTarget0))
                self.AddStep("SET_VAR_ILR_KERNEL_THRESHOLD", trinity.TriStepSetVariableStore("BloomWidth", (1.5/self.gatherTarget.width, 1.5/self.gatherTarget.height)))
                self.AddStep("SET_VAR_ILR_BLOOM", trinity.TriStepSetVariableStore("BloomMap", self.ilrMergeTarget))

                self.LoadILRSettings()

        else:
            self.RemoveStep("POST_PROCESS")
            self.RemoveStep("SET_VAR_POST_PROCESS_GATHER")
            self.RemoveStep("SET_POST_PROCESS_DEPTH_STENCIL")
            self.RemoveStep("RESTORE_DEPTH_STENCIL_FOR_TOOLS")
            self.RemoveStep("SET_POST_PROCESS_COMPOSITE_RT")
            self._ClearILRSteps()

            # Temp disabled.  Once ILR is on, it can't go off
            self.AddStep("SET_GATHER_RT", trinity.TriStepSetRenderTarget(self.backBufferRenderTarget))
            if self.backgroundScene is not None:
                self.AddStep("SET_BACKGROUND_RT", trinity.TriStepSetRenderTarget(self.backBufferRenderTarget))
            self.gatherTarget = None

            self.ilrBloomTarget0 = None
            self.ilrBloomTarget1 = None
            self.ilrBloomTarget2 = None
            self.ilrMergeTarget = None
            
        self.renderTargetList = (
                            blue.BluePythonWeakRef(self.backBufferDepthStencil), 
                            blue.BluePythonWeakRef(self.backBufferRenderTarget), 
                            blue.BluePythonWeakRef(self.prePassDepthStencil),  
                            blue.BluePythonWeakRef(self.prePassRenderTarget), 
                            blue.BluePythonWeakRef(self.lightAccumulationTarget),
                            blue.BluePythonWeakRef(self.ilrBloomTarget0),
                            blue.BluePythonWeakRef(self.ilrBloomTarget1),
                            blue.BluePythonWeakRef(self.ilrBloomTarget2),
                            blue.BluePythonWeakRef(self.ilrMergeTarget),
                            blue.BluePythonWeakRef(self.gatherTarget),
                            blue.BluePythonWeakRef(self.ssaoTarget),
                            )

    def _ClearILRSteps(self):
        self.RemoveStep("SET_VAR_ILR_BLOOM")
        self.RemoveStep("SET_VAR_ILR_REFLECTIONS_0")
        self.RemoveStep("SET_VAR_ILR_REFLECTIONS_1")
        self.RemoveStep("SET_VAR_ILR_THRESHOLD_0")
        self.RemoveStep("SET_VAR_ILR_KERNEL_0")
        self.RemoveStep("SET_ILR_BLOOM_RT_0")
        self.RemoveStep("RENDER_ILR_BLOOM_0")    
        self.RemoveStep("SET_VAR_ILR_THRESHOLD_1")
        self.RemoveStep("SET_VAR_ILR_KERNEL_1")
        self.RemoveStep("SET_ILR_BLOOM_RT_1")
        self.RemoveStep("RENDER_ILR_BLOOM_1") 
        self.RemoveStep("SET_VAR_ILR_MERGE_BLOOM0")
        self.RemoveStep("SET_VAR_ILR_MERGE_BLOOM1")
        self.RemoveStep("SET_VAR_ILR_MERGE_BLOOM2")
        self.RemoveStep("SET_ILR_MERGE_RT")
        self.RemoveStep("RENDER_ILR_MERGE")
        self.RemoveStep("SET_ILR_THRESHOLD_RT")
        self.RemoveStep("SET_VAR_ILR_KERNEL_THRESHOLD") 
        self.RemoveStep("RENDER_ILR_THRESHOLD")
        self.RemoveStep("SET_VAR_ILR_TINT_0") 
        self.RemoveStep("SET_VAR_ILR_TINT_1")

    def SetRenderTargets(self, 
                          backBufferDepthStencil,
                          backBufferRenderTarget, 
                          prePassDepthStencil, 
                          prePassRenderTarget, 
                          lightAccumulationTarget,
                          ilrBloomTarget0,
                          ilrBloomTarget1,
                          ilrBloomTarget2,
                          ilrMergeTarget,
                          gatherTarget,
                          ssaoTarget):
        """
        Set the required buffers on all the the renderjob steps.
        If any of these steps are missing, they will obviously not get set.
        """
        if prePassRenderTarget is not None:
            self.SetStepAttr("SET_PREPASS_RT", 'renderTarget', prePassRenderTarget)
        else:
            self.SetStepAttr("SET_PREPASS_RT", 'renderTarget', None)
 
        if lightAccumulationTarget is not None:
            self.SetStepAttr("SET_LIGHT_RT", 'renderTarget', lightAccumulationTarget)
        else:
            self.SetStepAttr("SET_LIGHT_RT", 'renderTarget', None) 
                  
        self.RemoveStep("SET_BACKGROUND_DEPTH_VAR")
        if prePassDepthStencil is not None:
            self.AddStep("SET_DEPTH", trinity.TriStepPushDepthStencil(prePassDepthStencil))
            self.AddStep("RESTORE_DEPTH", trinity.TriStepPopDepthStencil())
            # Only if the depth is a readable texture, can we set it as a variable store variable
            self.AddStep("SET_VAR_LIGHTS_DEPTH", trinity.TriStepSetVariableStore("LightPrePassDepthMap", prePassDepthStencil))
            # If we're running with SM_3_0_DEPTH the background scene has to have it's DepthMap variable set
            if trinity.GetShaderModel().endswith("DEPTH"):
                self.AddStep("SET_BACKGROUND_DEPTH_VAR", trinity.TriStepSetVariableStore("DepthMap", prePassDepthStencil))
        else:
            self.AddStep("SET_DEPTH", trinity.TriStepPushDepthStencil())
            self.AddStep("RESTORE_DEPTH", trinity.TriStepPopDepthStencil())

        # Variables dont like being initialized with "Null"
        self.AddStep("SET_VAR_LIGHTS_PREPASS", trinity.TriStepSetVariableStore("LightPrePassMap", prePassRenderTarget))
        self.AddStep("SET_VAR_LIGHTS", trinity.TriStepSetVariableStore("LightAccumulationMap", lightAccumulationTarget))

        self.AddStep("SET_VAR_SSAO", trinity.TriStepSetVariableStore("SSAOMap", ssaoTarget))

        if prePassRenderTarget is not None:
            self.EnableSSAO(self.ssaoEnabled)

        if gatherTarget is not None:
            self.SetStepAttr("SET_GATHER_RT", 'renderTarget', gatherTarget)
            if self.backgroundScene is not None:
                self.AddStep("SET_BACKGROUND_RT", trinity.TriStepSetRenderTarget(gatherTarget))
            self.AddStep("SET_VAR_POST_PROCESS_GATHER", trinity.TriStepSetVariableStore("GatherMap", gatherTarget))
            self.AddStep("SET_POST_PROCESS_DEPTH_STENCIL", trinity.TriStepPushDepthStencil(None))
            self.AddStep("SET_POST_PROCESS_COMPOSITE_RT", trinity.TriStepSetRenderTarget(backBufferRenderTarget))
        else:
            self.SetStepAttr("SET_GATHER_RT", 'renderTarget', backBufferRenderTarget)
            if self.backgroundScene is not None:
                self.AddStep("SET_BACKGROUND_RT", trinity.TriStepSetRenderTarget(backBufferRenderTarget))
            self.RemoveStep("SET_POST_PROCESS_DEPTH_STENCIL")
            self.RemoveStep("RESTORE_DEPTH_STENCIL_FOR_TOOLS")
            self.RemoveStep("SET_POST_PROCESS_COMPOSITE_RT")

        if ilrBloomTarget0 is not None:
            self.AddStep("SET_ILR_THRESHOLD_RT", trinity.TriStepSetRenderTarget(ilrBloomTarget0))
            self.AddStep("SET_VAR_ILR_KERNEL_THRESHOLD", trinity.TriStepSetVariableStore("BloomWidth", (1.5/gatherTarget.width, 1.5/gatherTarget.height)))
            self.AddStep("SET_VAR_ILR_BLOOM", trinity.TriStepSetVariableStore("BloomMap", ilrMergeTarget))

        else:
            self.RemoveStep("SET_ILR_THRESHOLD_RT")                   
            self.RemoveStep("SET_VAR_ILR_BLOOM")

        self.lightingLUT = blue.resMan.GetResource("res:/Graphics/Shared_Texture/Global/prepassLightLookup.dds")
        self.fresnelLUT = blue.resMan.GetResource("res:/Graphics/Shared_Texture/Global/prepassLightLookupFresnel.dds")
        self.AddStep( "SET_VAR_LIGHT_LUT",       trinity.TriStepSetVariableStore("LightingLUT", self.lightingLUT))
        self.AddStep( "SET_VAR_LIGHT_FRESNEL",   trinity.TriStepSetVariableStore("FresnelLUT", self.fresnelLUT))

    # Returns a tuple of backBufferDepthStencil, backBufferRenderTarget, prePassDepthStencil, prePassRenderTarget, lightAccumulationTarget weakrefs 
    def GetRenderTargets(self):   
        return self.renderTargetList
    
    def SetClearColor(self, color):
        """
        Sets the clear color, if a CLEAR renderstep exists.
        """
        step = self.GetStep("CLEAR_BACKGROUND_RT")
        if step is not None:
            step.color = color
            
        step = self.GetStep("CLEAR_GATHER_RT")
        if step is not None:
            step.color = color

    def GetInsiderVisualizationMenu(self):
        if not self.enabled:
            return [("None",None)]

        return self._CreateVisualizationMenu(self.visualizations)
    
    def _CreateVisualizationMenu(self, visualizations):
        """
        Recursive walk of the visualisations tree that reformats it into the menu tree
        specification.
        """
        menu = []
        # walk through the tree to construct the menu
        for entry in visualizations:
            if type(entry) == tuple:
                menu.append((entry[0], self._CreateVisualizationMenu(entry[1])))
            elif type(entry) == list:
                menu.append(self._CreateVisualizationMenu(entry))
            elif type(entry) == type("string"):
                pass
            elif hasattr(entry, "displayName"): # super hacky as isinstance doesn't seem to work here
                menu.append((entry.displayName, self.InsiderVisualizationSelected,[entry]))
            
        return menu     

    def InsiderVisualizationSelected(self, visualisation):
        """
        Applys a specific visualisation on the Incarna render job
        """
        if self.enabled:
            self.ApplyVisualization(visualisation)
