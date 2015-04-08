# Copyright (c) CCP 2012
"""
SSAO render job.
"""

import math
import random
import struct

from . import _trinity as trinity

SSAO_USE_NORMAL = 0
SSAO_NORMAL_FREE = 1

SSAO_HALF_RES_AO = 0
SSAO_FULL_RES_AO = 1


class SSAOOptions:
    """
    SSAO options (passed to RenderSSAOJob).
    """
    strength = 1
    radius = 3
    angleBias = 0
    radialAttenuation = 1
    randomTextureWidth = 4
    powerExponent = 1
    fogDistOfHalfStrength = 500
    fogAmount = 0
    shaderType = SSAO_NORMAL_FREE
    resolutionMode = SSAO_HALF_RES_AO
    numDirections = 6
    numSteps = 6
    maxFootprintRadius = 0.05
    blurRadius = 16
    blurSharpness = 5
    disableBlending = True


def GetSSAOCallbackStep(options, width, height, shaderSSAO, linearizeDepth, linearizeDepthAndPackAODepth):
    """
    Returns a callback function used for render job TriStepPythonCB.
    The function updates some camera-dependant parameters.
    """
    if options.resolutionMode == SSAO_HALF_RES_AO:
        downsampleFactor = 2.0
    else:
        downsampleFactor = 1.0

    aoWidth = width / downsampleFactor
    aoHeight = height / downsampleFactor


    def Callback():
        """
        A function used for callback step in the render job.
        Updates camera-dependent parameters.
        """
        fovY = trinity.GetFieldOfView()
        focalLen = (1.0 / math.tan(fovY * 0.5) * aoHeight / aoWidth, 1.0 / math.tan(fovY * 0.5))
        invFocalLen = (1.0 / focalLen[0], 1.0 / focalLen[1])
        focalLengthParams = (focalLen[0], focalLen[1], invFocalLen[0], invFocalLen[1])
        shaderSSAO.parameters['FocalLengthParams'].value = focalLengthParams
        
        zNear = trinity.GetFrontClip()
        zFar = trinity.GetBackClip()
        if zNear > 0 and zFar > 0:
            linA = 1.0 / zFar - 1.0 / zNear
            linB = 1.0 / zNear
        else:
            linA = 0.0
            linB = 0.0
        linearizeDepth.parameters['MiscParams'].z = linA
        linearizeDepth.parameters['MiscParams'].w = linB
        linearizeDepthAndPackAODepth.parameters['MiscParams'].z = linA
        linearizeDepthAndPackAODepth.parameters['MiscParams'].w = linB
        shaderSSAO.parameters['MiscParams'].z = linA
        shaderSSAO.parameters['MiscParams'].w = linB
    return Callback
    
    
def CreateMaterial(situation):
    """
    Creates SSAO material with given situation string.
    """
    material = trinity.Tr2ShaderMaterial()
    material.highLevelShaderName = 'SSAO'
    material.defaultSituation = situation
    return material
        
        
def SetMaterialConstants(options, width, height, linearizeDepth, linearizeDepthAndPackAODepth, blurX, blurY, shaderSSAO, randomTexture):
    """
    Set all constants for all used shader materials.
    """
    if options.resolutionMode == SSAO_HALF_RES_AO:
        downsampleFactor = 2.0
    else:
        downsampleFactor = 1.0

    aoWidth = width / downsampleFactor
    aoHeight = height / downsampleFactor
    angleBiasRad = (options.angleBias * math.pi / 180) + 1.e-5
    
    aoResolution = (aoWidth, aoHeight)
    invAOResolution = (1.0 / aoWidth, 1.0 / aoHeight)
    aoResolutionParams = (aoResolution[0], aoResolution[1], invAOResolution[0], invAOResolution[1])
    
    focalLengthParams = (1, 1, 1, 1)
    
    numDirs = ((options.numDirections + 1) / 2) * 2
    numSteps = options.numSteps
    tanAngleBias = math.tan(angleBiasRad)
    angleBias = angleBiasRad
    directionParams = (numDirs, numSteps, tanAngleBias, angleBias)
    
    r = options.radius
    sqrR = options.radius * options.radius
    invR = 1.0 / options.radius
    aspectRatio = aoHeight / aoWidth
    scaleParams = (r, sqrR, invR, aspectRatio)
    
    fullResolution = (width, height)
    invFullResolution = (1.0 / width, 1.0 / height)
    resolutionParams = (fullResolution[0], fullResolution[1], invFullResolution[0], invFullResolution[1])
    
    blurSigma = (options.blurRadius + 1.0) * 0.5
    halfBlurRadius = options.blurRadius * 0.5
    blurRadius = options.blurRadius
    blurSharpness = 1.44269504 * (options.blurSharpness * options.blurSharpness)
    blurFalloff = 1.44269504 / (2.0 * blurSigma * blurSigma)
    blurParams = (halfBlurRadius, blurRadius, blurSharpness, blurFalloff)
    
    deltaZ = options.fogDistOfHalfStrength - 1.0
    invRandTexSize = 1.0 / randomTexture.width
    fogK = 1.0 / (deltaZ * deltaZ)
    fogAmount = min(max(options.fogAmount, 0), 1)
    attenuation = options.radialAttenuation
    fogParams = (invRandTexSize, fogK, fogAmount, attenuation)

    powExponent = options.powerExponent
    contrast = options.strength / (1 - math.sin(angleBiasRad))
    miscParams = (powExponent, contrast, 0, 0)
    
    maxFootprintUV = min(options.maxFootprintRadius, 0.05)
    maxFootprintPixels = min(options.maxFootprintRadius, 0.05) * aoWidth
    filterParams = (maxFootprintUV, maxFootprintPixels, 0, 0)
    
    AddMaterialParam(linearizeDepth, 'MiscParams', miscParams)
    AddMaterialParam(linearizeDepthAndPackAODepth, 'MiscParams', miscParams)
    AddMaterialParam(blurX, 'ResolutionParams', resolutionParams)
    AddMaterialParam(blurX, 'BlurParams', blurParams)
    AddMaterialParam(blurY, 'ResolutionParams', resolutionParams)
    AddMaterialParam(blurY, 'BlurParams', blurParams)
    AddMaterialParam(blurY, 'FogParams', fogParams)
    AddMaterialParam(blurY, 'MiscParams', miscParams)
    AddMaterialParam(blurY, 'FilterParams', filterParams)

    AddMaterialParam(shaderSSAO, 'AOResolutionParams', aoResolutionParams)
    AddMaterialParam(shaderSSAO, 'FocalLengthParams', focalLengthParams)
    AddMaterialParam(shaderSSAO, 'DirectionParams', directionParams)
    AddMaterialParam(shaderSSAO, 'ScaleParams', scaleParams)
    AddMaterialParam(shaderSSAO, 'ResolutionParams', resolutionParams)
    AddMaterialParam(shaderSSAO, 'BlurParams', blurParams)
    AddMaterialParam(shaderSSAO, 'FogParams', fogParams)
    AddMaterialParam(shaderSSAO, 'MiscParams', miscParams)
    AddMaterialParam(shaderSSAO, 'FilterParams', filterParams)


def AddMaterialParam(material, name, value):
    """
    Helper function to add a new parameter to shader material.
    """
    if type(value) == trinity.TriTextureRes:
        param = trinity.TriTextureParameter()
        param.name = name
        param.SetResource(value)
    elif type(value) == trinity.Tr2RenderTarget:
        param = trinity.TriTextureParameter()
        param.name = name
        t = trinity.TriTextureRes(value)
        param.SetResource(t)
    elif type(value) == trinity.Tr2DepthStencil:
        param = trinity.TriTextureParameter()
        param.name = name
        t = trinity.TriTextureRes(value)
        param.SetResource(t)
    else:
        param = trinity.Tr2Vector4Parameter()
        param.name = name
        param.value = value
    material.parameters[name] = param
    

def CreateRandomTexture(options):
    """
    Creates a texture filled with random values needed for SSAO.
    """
    randomBitmap = trinity.Tr2HostBitmap(
        options.randomTextureWidth, 
        options.randomTextureWidth, 
        1, 
        trinity.PIXEL_FORMAT.R32G32B32A32_FLOAT)
    data = randomBitmap.GetRawData()
    values = []
    dataFormat = ''
    for i in range(options.randomTextureWidth * options.randomTextureWidth):
        angle = 2.0 * math.pi * random.random() / options.numDirections
        values.append(math.sin(angle))
        values.append(math.cos(angle))
        values.append(random.random())
        values.append(random.random())
        dataFormat += 'ffff'
    struct.pack_into(dataFormat, data[0], 0, *values)
    randomTexture = trinity.TriTextureRes()
    randomTexture.CreateFromHostBitmap(randomBitmap)
    return randomTexture
    
    
def AddStep(rj, name, step):
    """
    Helper function to add a new step to the render job.
    """
    step.name = name
    rj.steps.append(step)
    

def CreateSsaoRenderJob(options, width, height, outputRT):
    """
    Creates and returns an SSAO render job.
    Parameters:
        options - SSAOOptions object
        width - Width of the prepass depth texture
        height - Height of the prepass depth texture
        outputRT - output render target or None if RJ needs to output result in the current RT
    """
    randomTexture = CreateRandomTexture(options)
    if not randomTexture.isGood:
        return None

    linearizeDepth = CreateMaterial('linearizeDepth')

    # Since we have normal map from prepass we always use "normalFree" version
    # regardless of options
    shaderSSAO = CreateMaterial('normalFree useNormals')
    linearizeDepthAndPackAODepth = CreateMaterial('linearizeDepthAndPack')
    blurX = CreateMaterial('blurX')
    if not options.disableBlending:
        blurY = CreateMaterial('blurY blend')
    else:
        blurY = CreateMaterial('blurY')
    
    SetMaterialConstants(options, width, height, linearizeDepth, linearizeDepthAndPackAODepth, blurX, blurY, shaderSSAO, randomTexture)
    
    # Create RTs
    curHistoryAOZRT = trinity.Tr2RenderTarget(width, height, 1, trinity.PIXEL_FORMAT.R16G16_FLOAT)
    fullResAOZRT = trinity.Tr2RenderTarget(width, height, 1, trinity.PIXEL_FORMAT.R16G16_FLOAT)
    
    if options.resolutionMode == SSAO_HALF_RES_AO:
        linDepthRT = trinity.Tr2RenderTarget(width / 2, height / 2, 1, trinity.PIXEL_FORMAT.R32_FLOAT)
        halfResAORT = trinity.Tr2RenderTarget(width / 2, height / 2, 1, trinity.PIXEL_FORMAT.R8_UNORM)
        outputAOZ = halfResAORT
    else:
        linDepthRT = trinity.Tr2RenderTarget(width, height, 1, trinity.PIXEL_FORMAT.R32_FLOAT)
        outputAOZ = curHistoryAOZRT

    # Assign RTs to materials
    AddMaterialParam(shaderSSAO, 'DepthMap', linDepthRT)
    AddMaterialParam(shaderSSAO, 'RandomMap', randomTexture)
    if options.resolutionMode == SSAO_HALF_RES_AO:
        AddMaterialParam(linearizeDepthAndPackAODepth, 'SSAOMap', halfResAORT)
    AddMaterialParam(blurX, 'SSAOMap', curHistoryAOZRT)
    AddMaterialParam(blurY, 'SSAOMap', fullResAOZRT)
    
    # Rebind shaders
    linearizeDepth.BindLowLevelShader([])
    shaderSSAO.BindLowLevelShader([])
    linearizeDepthAndPackAODepth.BindLowLevelShader([])
    blurX.BindLowLevelShader([])
    blurY.BindLowLevelShader([])

    # Add steps
    rj = trinity.TriRenderJob()
    AddStep(rj, 'SAVE_DS', trinity.TriStepPushDepthStencil(None))
    AddStep(rj, 'SAVE_RT', trinity.TriStepPushRenderTarget())
    cb = GetSSAOCallbackStep(options, width, height, shaderSSAO, linearizeDepth, linearizeDepthAndPackAODepth)
    AddStep(rj, 'UPDATE_CONSTANTS', trinity.TriStepPythonCB(cb))
    
    AddStep(rj, 'SET_FULLSCREEN_STATES', trinity.TriStepSetStdRndStates(trinity.RM_FULLSCREEN))
    AddStep(rj, 'SET_LINEAR_DEPTH_RT', trinity.TriStepSetRenderTarget(linDepthRT))
    AddStep(rj, 'LINEARIZE_DEPTH', trinity.TriStepRenderFullScreenShader(linearizeDepth))
    
    AddStep(rj, 'SET_AO_RT', trinity.TriStepSetRenderTarget(outputAOZ))
    AddStep(rj, 'RENDER_AO', trinity.TriStepRenderFullScreenShader(shaderSSAO))
    
    if options.resolutionMode == SSAO_HALF_RES_AO:
        AddStep(rj, 'SET_TEMP_AO_RT', trinity.TriStepSetRenderTarget(curHistoryAOZRT))
        AddStep(rj, 'PACK_DEPTH_AND_AO', trinity.TriStepRenderFullScreenShader(linearizeDepthAndPackAODepth))

    AddStep(rj, 'SET_FULL_AO_RT', trinity.TriStepSetRenderTarget(fullResAOZRT))
    AddStep(rj, 'BLUR_X', trinity.TriStepRenderFullScreenShader(blurX))
    
    if outputRT is None:
        AddStep(rj, 'RESTORE_RT', trinity.TriStepPopRenderTarget())
    else:
        AddStep(rj, 'SET_OUTPUT_RT', trinity.TriStepSetRenderTarget(outputRT))
    
    AddStep(rj, 'BLUR_Y', trinity.TriStepRenderFullScreenShader(blurY))

    if outputRT:
        AddStep(rj, 'RESTORE_RT', trinity.TriStepPopRenderTarget())
    AddStep(rj, 'RESTORE_DS', trinity.TriStepPopDepthStencil())
    return rj
    
