# Copyright (c) CCP 2012
"""
Contains classes that take care of running post processing in space.
"""
import decometaclass

from .renderJobUtils import renderTargetManager as rtm
from . import _trinity as trinity

POST_PROCESS_ASTEROID_FOG = "ASTEROID_FOG"
POST_PROCESS_BLOOM_HIGH = "BLOOM_HIGH"
POST_PROCESS_BLOOM_LOW = "BLOOM_LOW"
POST_PROCESS_DESATURATE = "DESATURATE"
POST_PROCESS_INCURSION_OVERLAY = "INCURSION_OVERLAY"

POST_PROCESS_PATHS = {
    POST_PROCESS_ASTEROID_FOG: "res:/fisfx/postprocess/AsteroidFog.red",
    POST_PROCESS_INCURSION_OVERLAY: "res:/dx9/scene/postprocess/sanshaInfest.red",
    POST_PROCESS_DESATURATE: "res:/fisfx/postprocess/desaturate.red",
    POST_PROCESS_BLOOM_LOW: "res:/fisfx/postprocess/BloomExp.red",
    POST_PROCESS_BLOOM_HIGH: "res:/fisfx/postprocess/BloomVivid.red",
}


class EvePostProcess(object):
    """
    Objects of this class represent a single eve post process. Handles multipe
    and single step post processes.
    These objects are managed by EvePostProcessingJob.
    """
    def __init__(self, name, path, key=None):
        self.name = name
        self.path = path
        self.key = key
        self.postProcess = trinity.Load(path)

        self.steps = []

        self.sourceSize = (0, 0)
        self.swapSize = (0, 0)

        self.buffer1 = None
        self.buffer2 = None

    def RemoveSteps(self, rj):
        """ Removes all steps belonging to this post process from the renderjob. """
        for each in self.steps:
            rj.steps.fremove(each)

        self._ClearSteps()

    def Prepare(self, source):
        """
        Initialize buffers and variables used by this post process based on the source texture used.
        (source) -> The source render target which contains the image that this post process is applied to.
        """
        if source is None:
            return

        self.sourceSize = (source.width, source.height)

        if len(self.postProcess.stages) < 2:
            return

        width  = max(16, min(1024, (source.width  & ~15) / 2))
        height = max(16, min(1024, (source.height & ~15) / 2))
        self.swapSize = (width, height)

        if self.buffer1 is None or not rtm.CheckRenderTarget(self.buffer1, width, height, source.format):
            self.buffer1 = rtm.GetRenderTargetAL(width, height, 1, source.format, index=1)
            if self.buffer1 is not None:
                self.buffer1.name = "Post Process Bounce Target 1"

            self.buffer2 = rtm.GetRenderTargetAL(width, height, 1, source.format, index=2)
            if self.buffer2 is not None:
                self.buffer2.name = "Post Process Bounce Target 2"

    def _SwapBuffers(self):
        tempTarget = self.buffer1
        self.buffer1 = self.buffer2
        self.buffer2 = tempTarget

    def _AppendStep(self, rj, step, name=None):
        rj.steps.append(step)
        self.steps.append(step)
        if name is not None:
            step.name = name

    def AddSteps(self, rj):
        """
        Appends all steps neccessary to render this post process to the renderjob.
        """
        del self.steps[:]

        effects = self.postProcess.stages
        if len(effects) > 1:
            self._AppendStep(rj, trinity.TriStepPushRenderTarget(), "Store RT")
            value = (1.0 / self.swapSize[0], 1.0 / self.swapSize[1], self.swapSize[0], self.swapSize[1])
            self._AppendStep(rj, trinity.TriStepSetVariableStore("g_texelSize", value), "Set swap texelSize")
            self._AppendStep(rj, trinity.TriStepSetRenderTarget(self.buffer1), "Set RT")
            self._AppendStep(rj, trinity.TriStepRenderEffect(effects[0]), effects[0].name)

            for i in range(1, len(effects) - 1):
                self._AppendStep(rj, trinity.TriStepSetRenderTarget(self.buffer2), "Swap RT")
                self._AppendStep(rj, trinity.TriStepSetVariableStore("BlitCurrent", self.buffer1), "Override var BlitCurrent")
                self._AppendStep(rj, trinity.TriStepRenderEffect(effects[i]), effects[i].name)
                self._SwapBuffers()

            self._AppendStep(rj, trinity.TriStepSetVariableStore("BlitCurrent", self.buffer1), "Override var BlitCurrent")

            self._AppendStep(rj, trinity.TriStepPopRenderTarget(), "Restore RT")
            value = (1.0 / self.sourceSize[0], 1.0 / self.sourceSize[1], self.sourceSize[0], self.sourceSize[1])
            self._AppendStep(rj, trinity.TriStepSetVariableStore("g_texelSize", value), "Set source texelSize")

        self._AppendStep(rj, trinity.TriStepRenderEffect(effects[-1]), effects[-1].name)

    def _ClearSteps(self):
        del self.steps[:]

    def Release(self):
        """ Release resources used by this post process. """
        self._ClearSteps()
        self.buffer1 = None
        self.buffer2 = None


class EvePostProcessingJob(object):
    """
    This class is used to manage and post processing.
    """
    __cid__ = "trinity.TriRenderJob"
    __metaclass__ = decometaclass.BlueWrappedMetaclass
    _postProcessOrder = [
        POST_PROCESS_ASTEROID_FOG,
        POST_PROCESS_BLOOM_HIGH,
        POST_PROCESS_BLOOM_LOW,
        POST_PROCESS_INCURSION_OVERLAY,
        POST_PROCESS_DESATURATE
    ]

    def __init__(self, *args):
        self.resolveTarget = None
        self.destination = None
        self.liveCount = 0
        self.prepared = False
        self.key = None
        # If we want specific post processes to run first we add them to the postProcessOrder list
        # and add a None entry for them into the postProcesses list.
        self.postProcesses = []
        for _ in self._postProcessOrder:
            self.postProcesses.append(None)

    def _FindPostProcess(self, id):
        index = -1
        postProcess = None
        for postProcess in self.postProcesses:
            if getattr(postProcess, "name", None) == id:
                index = self.postProcesses.index(postProcess)
                break

        if index < 0 and id in self._postProcessOrder:
            index = self._postProcessOrder.index(id)
            postProcess = self.postProcesses[index]
        if index < 0:
            postProcess = None

        return postProcess, index

    def SetActiveKey(self, key=None):
        """
        Sets the post processing job's active key and rebuilds the render job. Only post processes with the matching
        or None keys will be run.
        If key is None all post processing is active.
        """
        if self.key == key:
            return

        dirty = False
        for pp in self.postProcesses:
            ppKey = getattr(pp, "key", None)
            if ppKey is None:
                continue

            if ppKey == key or ppKey == self.key:
                dirty = True
                break
        
        self.key = key
        if dirty:
            self.CreateSteps()

    def GetPostProcesses(self):
        """ Returns a list of all active post processes """
        postProcesses = []
        for each in self.postProcesses:
            if each is not None:
                postProcesses.append(each)
        return postProcesses

    def GetPostProcess(self, id):
        """
        Returns a post process(EvePostProcess) with the id provided(or None if it's not found)
        """
        return self._FindPostProcess(id)[0]

    def AddPostProcess(self, id, path=None, key=None):
        '''
        Adds a post process which is loaded from path and updates post processing steps
        (id) -> unique identifier for the post process
        (path) -> the value to assign to variable
        (key) -> optional parameter, post process will only be active if this is the current active key(see SetActiveKey)
        '''
        postProcess, i = self._FindPostProcess(id)

        if path is None:
            if id not in POST_PROCESS_PATHS:
                return
            path = POST_PROCESS_PATHS[id]

        if id in self._postProcessOrder:
            i = self._postProcessOrder.index(id)
            postProcess = self.postProcesses[i]
            if postProcess is None:
                self.liveCount += 1
                postProcess = self.postProcesses[i] = EvePostProcess(id, path, key)
            elif postProcess.path != path:
                postProcess = self.postProcesses[i] = EvePostProcess(id, path, key)
        elif postProcess is None:
            self.liveCount += 1
            postProcess = EvePostProcess(id, path, key)
            self.postProcesses.append(postProcess)
        elif postProcess.path != path:
            postProcess = self.postProcesses[i] = EvePostProcess(id, path, key)

        if self.prepared:
            postProcess.Prepare(self.source)
        
        self.CreateSteps()
        return postProcess

    def RemovePostProcess(self, id):
        '''
        Removes post process with id and rebuilds post processing steps
        (id) -> unique identifier for the post process
        '''
        index = -1
        for each in self.postProcesses:
            if getattr(each, "name", None) == id:
                index = self.postProcesses.index(each)
                break

        if index < 0:
            return

        self.liveCount -= 1

        self.postProcesses[index].RemoveSteps(self)
        self.postProcesses[index].Release()
        if id in self._postProcessOrder:
            self.postProcesses[index] = None
        else:
            self.postProcesses.remove(each)

        self.CreateSteps()

    def SetPostProcessVariable(self, id, variable, value):
        '''
        Sets a variable on a post process
        (id) -> the desired post process
        (variable) -> the variable name
        (value) -> the value to assign to variable
        '''
        for pp in self.postProcesses:
            if pp is not None and pp.name == id:
                for effect in pp.postProcess.stages:
                    for param in effect.parameters:
                        if param.name == variable:
                            param.value = value
                            return
                    for res in effect.resources:
                        if res.name == variable:
                            res.SetResource(value)
                            return

    def _AppendStep(self, name, step, rj=None):
        if rj is None:
            rj = self
        rj.steps.append(step)
        step.name = name

    def _DoPostProcess(self, pp, source):
        job = trinity.TriRenderJob()
        job.name = "Run Post Process " + str(pp.name)

        #Set the variable store, these are used by all eve space postprocessing
        self._AppendStep("Set var BlitOriginal", trinity.TriStepSetVariableStore("BlitOriginal", self.resolveTarget), job)
        self._AppendStep("Set var BlitCurrent", trinity.TriStepSetVariableStore("BlitCurrent", self.resolveTarget), job)
        pp.AddSteps(job)

        self._AppendStep(job.name, trinity.TriStepRunJob(job))

    def Prepare(self, source, blitTexture, destination=None):
        """
        Prepare the renderjob and it's post processes.
        (source) -> The source image used for post processing
        (blitTexture) -> Used as the source texture for actual post processes,
                         Must have same format and dimensions as source.
        (destination) -> Optional. The render target will render final result into this
                         render target. Otherwise the active render target will be used.
        """
        self.prepared = True
        self.resolveTarget = blitTexture
        self.source = source
        self.destination = destination
        for each in self.postProcesses:
            if each is not None:
                each.Prepare(source)

    def Release(self):
        """
        Release all resources associated with this render job and it's post processes. Clears the job.
        """
        self.prepared = False
        self.ClearSteps()
        self.resolveTarget = None
        self.source = None
        self.destination = None
        for each in self.postProcesses:
            if each is not None:
                each.Release()

    def CreateSteps(self):
        """
        Rebuild this renderjob. If the job has not been prepared it will be empty.
        """
        if not self.prepared:
            return

        self.ClearSteps()

        if self.liveCount < 1:
            return

        if self.source.width < 1 or self.source.height < 1:
            return

        postProcesses = []
        for each in self.postProcesses:
            ppKey = getattr(each, "key", None)
            if each is not None and (ppKey is None or ppKey == self.key):
                postProcesses.append(each)

        if self.destination is not None:
            self._AppendStep("Push Destination RT", trinity.TriStepPushRenderTarget(self.destination))

        if len(postProcesses) > 1:
            self._AppendStep("Push Source RT", trinity.TriStepPushRenderTarget(self.source))

        self._AppendStep("Push null depth stencil", trinity.TriStepPushDepthStencil(None))

        if self.resolveTarget is not None:
            self._AppendStep("Resolve render target", trinity.TriStepResolve(self.resolveTarget, self.source))

        self._AppendStep("Set render states", trinity.TriStepSetStdRndStates(trinity.RM_FULLSCREEN))
        value = (1.0 / self.source.width, 1.0 / self.source.height, self.source.width, self.source.height)
        self._AppendStep("Set var texelSize", trinity.TriStepSetVariableStore("g_texelSize", value))
        for pp in postProcesses:
            if pp == postProcesses[-1] and len(postProcesses) > 1:
                # Render the final post process to the destination surface
                self._AppendStep("Pop source RT", trinity.TriStepPopRenderTarget())

            self._DoPostProcess(pp, self.resolveTarget)

            if pp != postProcesses[-1] and self.resolveTarget is not None:
                self._AppendStep("Resolve render target", trinity.TriStepResolve(self.resolveTarget, self.source))

        if self.destination is not None:
            self._AppendStep("Pop destination RT", trinity.TriStepPopRenderTarget())
        self._AppendStep("Restore depth stencil", trinity.TriStepPopDepthStencil())

    def ClearSteps(self):
        """ Clears all steps from this render job. """
        for each in self.postProcesses:
            if each is not None:
                each.RemoveSteps(self)
                
        del self.steps[:]

