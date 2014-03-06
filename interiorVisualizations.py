"""
Contains code used to setup the visualizations needed for sceneRenderJobInterior, allowing python to
drive how visualizations are managed, and disable render steps if needed.
"""

import blue
from . import _trinity as trinity


class VisualizationBase(object):
    """
    This base class encapsulates a small amount of logic for changing and restoring renderjob step states 
    """
    displayName = "Base Visualization, do not use"

    def __init__(self):
        self.originalStepStates = []

    def SetStepAttr(self, rj, stepKey, attr, value):
        """
        Set an attribute on a renderjob step and store it, so that we can restore it later
        """
        if rj.HasStep(stepKey):
            self.originalStepStates.append((stepKey, attr, getattr(rj.GetStep(stepKey), attr)))
            rj.SetStepAttr(stepKey, attr, value)

    def RestoreStepStates(self, rj):
        """
        Restore any changes made to steps by self.SetStepAttr
        """
        for step, attr, state in self.originalStepStates:
            rj.SetStepAttr(step, attr, state)
    

class VisualizerStepBase(VisualizationBase):
    """
    Base class for writing visualizations that only require SSAO to be disabled and
    a visualization step to be added
    """
    displayName = "VisualizerStepBase"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_NONE

    def __init__(self):
        VisualizationBase.__init__(self)
        self.renderJobs = []
        self.wireframeModeEnabled = False
        self.ssaoState = None

    def ApplyVisualization(self, rj):
        self.renderJobs.append(rj)
        rj.AddStep( "SET_VISUALIZATION", trinity.TriStepSetVisualizationMode( rj.GetScene(), self.visualizationMode ) )
        ssao = rj.GetStep("RENDER_SSAO")
        if ssao is not None:
            self.ssaoState = ssao.enabled
        else:
            self.ssaoState = None
        self.SetStepAttr(rj, "RENDER_SSAO", 'enabled', False)

    def RemoveVisualization(self, rj):
        rj.RemoveStep("SET_VISUALIZATION")
        self.SetEnableWireframeMode(False)
        
        if self.ssaoState is not None:
            ssao = rj.GetStep("RENDER_SSAO")
            if ssao is not None:
                ssao.enabled = self.ssaoState
        self.ssaoState = None

        if rj.GetScene():
            rj.GetScene().visualizeMethod = 0

        self.RestoreStepStates(rj)
        self.renderJobs.remove(rj)

    def SetEnableWireframeMode(self, enable):
        self.wireframeModeEnabled = enable
        if self.wireframeModeEnabled :
            for eachRenderJob in self.renderJobs:
                eachRenderJob.AddStep("ENABLE_WIREFRAME", trinity.TriStepEnableWireframeMode(True))                    
                eachRenderJob.AddStep("RESTORE_WIREFRAME", trinity.TriStepEnableWireframeMode(False))                    
        else:
            for eachRenderJob in self.renderJobs:
                eachRenderJob.RemoveStep("ENABLE_WIREFRAME")
                eachRenderJob.RemoveStep("RESTORE_WIREFRAME")


class EveAlbedoVisualization(VisualizationBase):
    """
    Shows surface albedo colors.
    """
    displayName = "Albedo"
    def ApplyVisualization(self, rj):
        """
        Applies visualization using a global situation flag
        """
        trinity.AddGlobalSituationFlags(['OPT_VISUALIZE_TEXTURES'])
        trinity.RebindAllShaderMaterials()
    def RemoveVisualization(self, rj):
        """
        Removes visualization using a global situation flag
        """
        trinity.RemoveGlobalSituationFlags(['OPT_VISUALIZE_TEXTURES'])
        trinity.RebindAllShaderMaterials()


class DisableVisualization(VisualizerStepBase):
    """
    No visualizer - use normal rendering
    """
    displayName = "Disable visualizations"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_NONE

    def ApplyVisualization(self, rj):
        self.renderJobs.append(rj)
        rj.AddStep("SET_VISUALIZATION", trinity.TriStepSetVisualizationMode(rj.GetScene(), self.visualizationMode))


class WhiteVisualization(VisualizerStepBase):
    """ Pixel shader returns white (useful to verify that something is output) """
    displayName = "White"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_WHITE


class ObjectNormalVisualization(VisualizerStepBase):
    """ Normal from vertices """
    displayName = "Object Normal"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_OBJECT_NORMAL

class TangentVisualization(VisualizerStepBase):
    """ Tangent from vertices """
    displayName = "Tangent"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_TANGENT


class BiTangentVisualization(VisualizerStepBase):
    """ Bitangent from vertices """
    displayName = "BiTangent"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_BITANGENT
    

class TexCoord0Visualization(VisualizerStepBase):
    """ Texture coordinate 0 """
    displayName = "TexCoord0"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_TEXCOORD0


class TexCoord1Visualization(VisualizerStepBase):
    """ Texture coordinate 1 """
    displayName = "TexCoord1"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_TEXCOORD1


class TexelDensityVisualization(VisualizerStepBase):
    """ Density of texels mapped through texture coordinate 0 """
    displayName = "Texel Density"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_TEXELDENSITY0


class NormalMapVisualization(VisualizerStepBase):
    """ Tangent space normal from map """
    displayName = "Normal Map Only"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_NORMALMAP
    

class DiffuseMapVisualization(VisualizerStepBase):
    """ Displays the diffuse Map """
    displayName = "Diffuse Map"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_DIFFUSEMAP


class SpecularMapVisualization(VisualizerStepBase):
    """ Displays the specular Map """
    displayName = "Specular Map"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_SPECULARMAP
    

class OverdrawVisualization(VisualizerStepBase):
    """ See the overdraw of the scene """
    displayName = "Overdraw"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_OVERDRAW
    

class EnlightenOnlyVisualization(VisualizerStepBase):
    """ Displays the only the enlighten component of lighting """
    displayName = "Enlighten Lighting Only"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_EN_ONLY


class EnlightenTargetDetailVisualization(VisualizerStepBase):
    """ Displays target geometry in wireframe, detail geometry in red """
    displayName = "Enlighten Target/Detail"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_EN_TARGET_DETAIL
    

class EnlightenOutputDensityVisualization(VisualizerStepBase):
    """ Displays the size of enlighten pixels """
    displayName = "Enlighten Output Density"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_EN_OUTPUT_DENSITY


class EnlightenAlbedoVisualization(VisualizerStepBase):
    """ Displays the material colour used for light bounces in enlighten """
    displayName = "Enlighten Albedo"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_EN_ALBEDO


class EnlightenEmissiveVisualization(VisualizerStepBase):
    """ Displays the emissive colour on statics used for enlighten """
    displayName = "Enlighten Emissive"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_EN_EMISSIVE


class EnlightenObjectTexcoordVisualization(VisualizerStepBase):
    """ Displays enlighten object texture coordinates (statics only) """
    displayName = "Enlighten Object Texcoords"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_EN_OBJECT_TEXCOORD


class EnlightenNaughtyPixelsVisualization(VisualizerStepBase):
    """ Displays enlighten pixels with poor projection to the target mesh """
    displayName = "Enlighten Naughty Pixels"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_EN_NAUGHTY_PIXELS
    

class EnlightenDetailChartsVisualization(VisualizerStepBase):
    """ Displays enlighten lightmap charts """
    displayName = "Enlighten Detail Mesh Charts"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_EN_CHARTS


class EnlightenTargetChartsVisualization(VisualizerStepBase):
    """ Displays enlighten lightmap charts """
    displayName = "Enlighten Target Mesh Charts"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_EN_TARGET_CHARTS


class DepthVisualization(VisualizerStepBase):
    """ Displays depth buffer of the scene """
    displayName = "Depth"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_DEPTH


class AllLightingVisualization(VisualizerStepBase):
    """ Displays cummulative direct and secondary lighting """
    displayName = "All Lighting"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_ALL_LIGHTING


class PrePassLightNormalVisualization(VisualizerStepBase):
    """ Shows normal in worldspace from light pre-pass texture """
    displayName = "PrePass Lighting Normal"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_LIGHT_PRE_PASS_NORMALS


class PrePassLightDepthVisualization(VisualizerStepBase):
    """ Shows depth in clip space from light pre-pass texture """
    displayName = "PrePass Lighting Depth"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_LIGHT_PRE_PASS_DEPTH


class PrePassLightWorldPositionVisualization(VisualizerStepBase):
    """ Shows world position from light pre-pass texture """
    displayName = "PrePass Lighting World Position"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_LIGHT_PRE_PASS_WORLD_POSITION
        

class PrePassLightingOnlyVisualization(VisualizerStepBase):
    """ Displays the accumulated pre-pass lighting contribution """
    displayName = "PrePass Lighting Only"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_LIGHT_PRE_PASS_LIGHTING


class PrePassLightOverdrawVisualization(VisualizerStepBase):
    """ Shows light overdraw in prepass rendering as increasingly red pixels """
    displayName = "Light Overdraw"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_LIGHT_PRE_PASS_LIGHT_OVERDRAW
        

class PrePassLightingDiffuseVisualization(VisualizerStepBase):
    """ Displays the accumulated pre-pass diffuse lighting contribution """
    displayName = "PrePass Diffuse Lighting Only"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_LIGHT_PRE_PASS_DIFFUSE_LIGHTING
        

class PrePassLightingSpecularVisualization(VisualizerStepBase):
    """ Displays the accumulated pre-pass specular lighting contribution """
    displayName = "PrePass Specular Lighting Only"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_LIGHT_PRE_PASS_SPECULAR_LIGHTING


class OcclusionVisualization(VisualizerStepBase):
    """ Shows light overdraw in prepass rendering as increasingly red pixels """
    displayName = "Occlusion Geometry"
    visualizationMode = trinity.Tr2InteriorVisualizerMethod.VM_OCCLUSION
    

class LightVolumeVisualizationBase(VisualizationBase):
    """
    A base class for visualizing light volumes
    """
    displayName = "Light Volumes"
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_SHADOW_RESOLUTION

    def __init__(self):
        VisualizationBase.__init__(self)
        self.lightStates = []

    def ShouldLightBeVisualized(self, light):
        return True

    def ApplyVisualization(self, rj):        
        scene = rj.GetScene()
        if scene is not None:
            for light in scene.lights:
                if self.ShouldLightBeVisualized(light):
                    self.lightStates.append((blue.BluePythonWeakRef(light), light.renderDebugInfo, light.renderDebugType))
                    light.renderDebugInfo = True
                    light.renderDebugType = self.lightDebugRenderType

    def RemoveVisualization(self, rj):
        self.RestoreStepStates(rj)
        for lightWR, rDI, rDT in self.lightStates:
            light = lightWR.object
            if light is not None:
                light.renderDebugInfo = rDI
                light.renderDebugType = rDT
        


class LightVolumeColorBaseVisualization(LightVolumeVisualizationBase):
    """
    A base class for rendering of light volumes    
    """
    displayName = "Light Volume base"

    def ShouldLightBeVisualized(self, light):
        return True


class LightVolumeWhiteVisualization(LightVolumeColorBaseVisualization):
    """ Renders all lights as volumes with a white color """
    displayName = "Light Volumes (White)"
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_WHITE_VOLUMES
        

class LightVolumeNormalVisualization(LightVolumeColorBaseVisualization):
    """ Renders all lights as volumes with their natural colors """
    displayName = "Light Volumes (Source)"
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_LIGHT_COLOR


class LightVolumeShadowResolutionVisualization(LightVolumeColorBaseVisualization):
    """ Renders all lights as volumes with colors representing shadow resolution """
    displayName = "Light Volumes (Shadow Resolution)"
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_SHADOW_RESOLUTION
    

class LightVolumeShadowRelativeResolutionVisualization(LightVolumeColorBaseVisualization):
    """ Renders all lights as volumes with colors representing shadow relative resolution """
    displayName = "Light Volumes (Shadow Relative Resolution)"
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_SHADOW_RELATIVE_RESOLUTION
    

class PrimaryLightVolumeColorBaseVisualization(LightVolumeVisualizationBase):
    """
    A base class for rendering of primary light volumes    
    """
    displayName = "Primary Light Volume base"

    def ShouldLightBeVisualized(self, light):
        if getattr(light, 'primaryLighting', True):
            return True
        else:
            return False


class PrimaryLightVolumeWhiteVisualization(PrimaryLightVolumeColorBaseVisualization):
    """ Renders primary lights as volumes with a white color """
    displayName = "Primary Light Volumes (White)"
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_WHITE_VOLUMES
    

class PrimaryLightVolumeNormalVisualization(PrimaryLightVolumeColorBaseVisualization):
    """ Renders primary lights as volumes with their natural colors """
    displayName = "Primary Light Volumes (Source)"
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_LIGHT_COLOR
    

class PrimaryLightVolumeShadowResolutionVisualization(PrimaryLightVolumeColorBaseVisualization):
    """ Renders primary lights as volumes with colors representing shadow resolution """
    displayName = "Primary Light Volumes (Shadow Resolution)"
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_SHADOW_RESOLUTION


class PrimaryLightVolumeShadowRelativeResolutionVisualization(PrimaryLightVolumeColorBaseVisualization):
    """ Renders primary lights as volumes with colors representing shadow relative resolution """
    displayName = "Primary Light Volumes (Shadow Relative Resolution)"
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_SHADOW_RELATIVE_RESOLUTION


class SecondaryLightVolumeColorBaseVisualization(LightVolumeVisualizationBase):
    """
    A base class for rendering of secondary light volumes    
    """
    displayName = "Secondary Light Volume base"

    def ShouldLightBeVisualized(self, light):
        if getattr(light, 'secondaryLighting', True):
            return True
        else:
            return False


class SecondaryLightVolumeWhiteVisualization(SecondaryLightVolumeColorBaseVisualization):
    """ Renders secondary lights as volumes with a white color """
    displayName = "Secondary Light Volumes (White)" 
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_WHITE_VOLUMES


class SecondaryLightVolumeNormalVisualization(SecondaryLightVolumeColorBaseVisualization):
    """ Renders secondary lights as volumes with their natural colors """
    displayName = "Secondary Light Volumes (Source)"
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_LIGHT_COLOR


class SecondaryLightVolumeShadowResolutionVisualization(SecondaryLightVolumeColorBaseVisualization):
    """ Renders secondary lights as volumes with colors representing shadow resolution """
    displayName = "Secondary Light Volumes (Shadow Resolution)" 
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_SHADOW_RESOLUTION
        

class SecondaryLightVolumeShadowRelativeResolutionVisualization(SecondaryLightVolumeColorBaseVisualization):
    """ Renders secondary lights as volumes with colors representing shadow relative resolution """
    displayName = "Secondary Light Volumes (Shadow Relative Resolution)"
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_SHADOW_RELATIVE_RESOLUTION
    

class ShadowcastingLightVolumeColorBaseVisualization(LightVolumeVisualizationBase):
    """
    A base class for rendering of shadonwcasting light volumes    
    """
    displayName = "Shadowcasting Light Volume base"

    def ShouldLightBeVisualized(self, light):
        if getattr(light, 'shadowCasterTypes', True):
            return True
        else:
            return False


class ShadowcastingLightVolumeWhiteVisualization(ShadowcastingLightVolumeColorBaseVisualization):
    """ Renders secondary lights as volumes with a white color """
    displayName = "Shadowcasting Light Volumes (White)"
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_WHITE_VOLUMES
        

class ShadowcastingLightVolumeNormalVisualization(ShadowcastingLightVolumeColorBaseVisualization):
    """ Renders shadowcasting lights as volumes with their natural colors """
    displayName = "Shadowcasting Light Volumes (Source)"
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_LIGHT_COLOR
    

class ShadowcastingLightVolumeShadowResolutionVisualization(ShadowcastingLightVolumeColorBaseVisualization):
    """ Renders shadowcasting lights as volumes with colors representing shadow resolution """
    displayName = "Shadowcasting Light Volumes (Shadow Resolution)"
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_SHADOW_RESOLUTION


class ShadowcastingLightVolumeShadowRelativeResolutionVisualization(ShadowcastingLightVolumeColorBaseVisualization):
    """ Renders shadowcasting lights as volumes with colors representing shadow relative resolution """
    displayName = "Shadowcasting Light Volumes (Shadow Relative Resolution)"
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_SHADOW_RELATIVE_RESOLUTION
    

class TransparentLightVolumeColorBaseVisualization(LightVolumeVisualizationBase):
    """
    Renders lights which affect transparent objects
    """
    displayName = "Transparent Light Volume base"

    def ShouldLightBeVisualized(self, light):
        if getattr(light, 'affectTransparentObjects', True):
            return True
        else:
            return False


class TransparentLightVolumeWhiteVisualization(TransparentLightVolumeColorBaseVisualization):
    """ Renders lights which affect transparent objects with white colored volume """
    displayName = "Transparent Light Volumes (White)"
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_WHITE_VOLUMES


class TransparentLightVolumeNormalVisualization(TransparentLightVolumeColorBaseVisualization):
    """ Renders lights which affect transparent objects with normal colored volume """
    displayName = "Transparent Light Volumes (Source)"
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_LIGHT_COLOR


class TransparentLightVolumeShadowResolutionVisualization(TransparentLightVolumeColorBaseVisualization):
    """ Renders lights which affect transparent objects with colors representing shadow resolution """
    displayName = "Transparent Light Volumes (Shadow Resolution)"
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_SHADOW_RESOLUTION
        

class TransparentLightVolumeShadowRelativeResolutionVisualization(TransparentLightVolumeColorBaseVisualization):
    """ Renders lights which affect transparent objects with colors representing shadow relative resolution """
    displayName = "Transparent Light Volumes (Shadow Relative Resolution)"
    lightDebugRenderType = trinity.Tr2InteriorLightDebugRenderMode.DI_SHADOW_RELATIVE_RESOLUTION
      
      
class WoDEnlightenOnlyVisualization(VisualizerStepBase):
    """
    Displays only the enlighten component of lighting
    """
    displayName = "Enlighten Lighting Only"

    def __init__(self):
        VisualizerStepBase.__init__(self)

    def ApplyVisualization(self, rj):
        VisualizerStepBase.ApplyVisualization(self, rj)
        rj.gatherShader.parameters["VisFlags1"].value = [0.0,0.0,0.0,1.0]
        rj.gatherShader.parameters["VisFlags2"].value = [0.0,0.0,0.0,0.0]
        rj.SetStepAttr("RENDER_LIGHTS", "enabled", False)
        rj.gatherShader.BindLowLevelShader(['viz'])

    def RemoveVisualization(self, rj):
        VisualizerStepBase.RemoveVisualization(self, rj)
        rj.gatherShader.BindLowLevelShader(['none'])
        rj.SetStepAttr("RENDER_LIGHTS", "enabled", True)
       

class WoDDiffuseLightOnlyVisualization(VisualizerStepBase):
    """
    Displays only the diffuse component of lighting
    """
    displayName = "Diffuse Lighting Only"

    def __init__(self):
        VisualizerStepBase.__init__(self)

    def ApplyVisualization(self, rj):        
        VisualizerStepBase.ApplyVisualization(self, rj)
        rj.gatherShader.parameters["VisFlags1"].value = [0.0,0.0,0.0,1.0]
        rj.gatherShader.parameters["VisFlags2"].value = [0.0,0.0,0.0,0.0]
        rj.gatherShader.BindLowLevelShader(['viz'])

    def RemoveVisualization(self, rj):
        VisualizerStepBase.RemoveVisualization(self, rj)
        rj.gatherShader.BindLowLevelShader(['none'])


class WoDSpecularLightOnlyVisualization(VisualizerStepBase):
    """
    Displays only the specular component of lighting
    """
    displayName = "Specular Lighting Only"

    def __init__(self):
        VisualizerStepBase.__init__(self)

    def ApplyVisualization(self, rj):
        VisualizerStepBase.ApplyVisualization(self, rj)
        rj.gatherShader.parameters["VisFlags1"].value = [0.0,0.0,0.0,0.0]
        rj.gatherShader.parameters["VisFlags2"].value = [1.0,0.0,0.0,0.0]
        rj.gatherShader.BindLowLevelShader(['viz'])

    def RemoveVisualization(self, rj):
        VisualizerStepBase.RemoveVisualization(self, rj)
        rj.gatherShader.BindLowLevelShader(['none'])

       
class WoDDiffuseOnlyVisualization(VisualizerStepBase):
    """
    Displays only the diffuse g-buffer
    """
    displayName = "Diffuse Color Only"

    def __init__(self):
        VisualizerStepBase.__init__(self)

    def ApplyVisualization(self, rj):
        VisualizerStepBase.ApplyVisualization(self, rj)
        rj.gatherShader.parameters["VisFlags1"].value = [0.0,1.0,0.0,0.0]
        rj.gatherShader.parameters["VisFlags2"].value = [0.0,0.0,0.0,0.0]
        rj.gatherShader.BindLowLevelShader(['viz'])

    def RemoveVisualization(self, rj):
        VisualizerStepBase.RemoveVisualization(self, rj)
        rj.gatherShader.BindLowLevelShader(['none'])
       

class WoDSpecularOnlyVisualization(VisualizerStepBase):
    """
    Displays only the specular g-buffer
    """
    displayName = "Specular Color Only"

    def __init__(self):
        VisualizerStepBase.__init__(self)

    def ApplyVisualization(self, rj):
        VisualizerStepBase.ApplyVisualization(self, rj)
        rj.gatherShader.parameters["VisFlags1"].value = [0.0,0.0,1.0,0.0]
        rj.gatherShader.parameters["VisFlags2"].value = [0.0,0.0,0.0,0.0]
        rj.gatherShader.BindLowLevelShader(['viz'])

    def RemoveVisualization(self, rj):
        VisualizerStepBase.RemoveVisualization(self, rj)
        rj.gatherShader.BindLowLevelShader(['none'])
       

class WoDFinalDiffuseVisualization(VisualizerStepBase):
    """
    Displays only the diffuse result (no specular)
    """
    displayName = "Diffuse result Only"

    def __init__(self):
        VisualizerStepBase.__init__(self)

    def ApplyVisualization(self, rj):
        VisualizerStepBase.ApplyVisualization(self, rj)
        rj.gatherShader.parameters["VisFlags1"].value = [0.0,0.0,0.0,0.0]
        rj.gatherShader.parameters["VisFlags2"].value = [0.0,1.0,0.0,0.0]
        rj.gatherShader.BindLowLevelShader(['viz'])

    def RemoveVisualization(self, rj):
        VisualizerStepBase.RemoveVisualization(self, rj)
        rj.gatherShader.BindLowLevelShader(['none'])


class WoDFinalSpecularVisualization(VisualizerStepBase):
    """
    Displays only the specular result (no diffuse)
    """
    displayName = "Specular result Only"

    def __init__(self):
        VisualizerStepBase.__init__(self)

    def ApplyVisualization(self, rj):
        VisualizerStepBase.ApplyVisualization(self, rj)
        rj.gatherShader.parameters["VisFlags1"].value = [0.0,0.0,0.0,0.0]
        rj.gatherShader.parameters["VisFlags2"].value = [0.0,0.0,1.0,0.0]
        rj.gatherShader.BindLowLevelShader(['viz'])

    def RemoveVisualization(self, rj):
        VisualizerStepBase.RemoveVisualization(self, rj)
        rj.gatherShader.BindLowLevelShader(['none'])       
       

class WoDNormalsVisualization(VisualizerStepBase):
    """
    Displays only the normals from the g-buffer
    """
    displayName = "Normals as Color"

    def __init__(self):
        VisualizerStepBase.__init__(self)

    def ApplyVisualization(self, rj):
        VisualizerStepBase.ApplyVisualization(self, rj)
        rj.gatherShader.parameters["VisFlags1"].value = [1.0,0.0,0.0,0.0]
        rj.gatherShader.parameters["VisFlags2"].value = [0.0,0.0,0.0,0.0]
        rj.gatherShader.BindLowLevelShader(['viz'])

    def RemoveVisualization(self, rj):
        VisualizerStepBase.RemoveVisualization(self, rj)
        rj.gatherShader.BindLowLevelShader(['none'])
       
       
class WoDSurfaceStylesVisualization(VisualizerStepBase):
    """
    Displays only the surface styles in RG
    """
    displayName = "Surface Style IDs"

    def __init__(self):
        VisualizerStepBase.__init__(self)

    def ApplyVisualization(self, rj):
        VisualizerStepBase.ApplyVisualization(self, rj)
        rj.gatherShader.parameters["VisFlags1"].value = [0.0,0.0,0.0,0.0]
        rj.gatherShader.parameters["VisFlags2"].value = [0.0,0.0,0.0,1.0]
        rj.gatherShader.BindLowLevelShader(['viz'])

    def RemoveVisualization(self, rj):
        VisualizerStepBase.RemoveVisualization(self, rj)
        rj.gatherShader.BindLowLevelShader(['none'])
