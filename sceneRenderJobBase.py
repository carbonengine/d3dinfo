import blue
import decometaclass
import geo2

from . import _singletons
from . import _trinity as trinity
from .renderJobUtils import renderTargetManager as rtm
from .renderJob import renderJobs

try:
    import stackless
    usingStackless = True
except ImportError:
    usingStackless = False


class SceneRenderJobBase(object):
    __cid__       = "trinity.TriRenderJob"
    __metaclass__ = decometaclass.BlueWrappedMetaclass

    # This is the order that the steps should appear in the renderjob
    # You must populate this on child classes
    renderStepOrder = []

    # This is a template for creating quad and multi-view renderjobs
    # it breaks things down into passes, with shared steps in between
    multiViewStages = None
    visualizations = []
    stereoEnabled = False

    def Start(self):
        """
        Schedule the renderjob to run
        """
        if not self.scheduled:
            renderJobs.recurring.insert(0, self)
            self.scheduled = True

    def Pause(self):
        """
        Schedule the renderjob to run
        """
        if self.scheduled:
            self.UnscheduleRecurring()
            self.scheduled = False

    def UnscheduleRecurring(self, scheduledRecurring=None):
        """
        Remove this job from the given list of render jobs. If no list is given,
        remove this job from the device's scheduledRecurring list.
        """
        if scheduledRecurring is None:
            scheduledRecurring = renderJobs.recurring

        if self in scheduledRecurring:
            scheduledRecurring.remove(self)

    def ScheduleOnce(self):
        """
        Add this job to the device's list of jobs to run once
        """
        if not self.enabled:
            self.enabled = True
            try:
                self.DoPrepareResources()
            except trinity.D3DError:
                pass
                          
        renderJobs.once.append(self)
    
    def WaitForFinish(self):
        """
        Block until this job has finished.
        """
        while not ((self.status == trinity.RJ_DONE) or (self.status == trinity.RJ_FAILED)):
            if usingStackless:
                blue.synchro.Yield()
            else:
                blue.os.Pump()

    def Disable(self):
        """
        Disable the renderjob - prevent it from recreating resources, and make sure that it isn't scheduled 
        """
        self.enabled = False
        self.DoReleaseResources(1)
        if self.scheduled:
            renderJobs.recurring.remove(self)
            self.scheduled = False

    def Enable(self, schedule=True):
        """
        Make sure that the renderjob is ready to run. Call DoPrepareResources, then schedule it.
        """
        self.enabled = True
        try:
            self.DoPrepareResources()
        except trinity.D3DError:
            pass
        if schedule:
            self.Start()

    def GetRenderStepOrderList(self):
        """
        Gets the list of steps to use to determine where to add a new step.
        In particular, this allows us to use different render steps for multi-view stages
        """
        if self.multiViewStages is not None and self.currentMultiViewStageKey is not None: 
            for stageName, sharedSetupStep, stepList in self.multiViewStages : 
                if stageName == self.currentMultiViewStageKey:
                    return stepList
            return None

        return self.renderStepOrder

    def _AddStereoStep(self, step):
        """
        Adds the given step the second time for the right eye. Assumes that the step
        was already inserted into correct position in the steps list for the left eye.
        If the stereoEnabled flag is False the function does nothing.
        """
        if not self.stereoEnabled:
            return
        index = self.steps.index(step)
        startLeft = -1
        startRight = -1
        for i, step in enumerate(self.steps):
            if step.name == "UPDATE_STEREO":
                startLeft = i
            elif step.name == "UPDATE_STEREO_RIGHT":
                startRight = i
        if startLeft < 0 or startRight < 0:
            return
        if index > startLeft and index < startRight:
            self.steps.insert(startRight + index - startLeft, step)
        elif index > startRight:
            self.steps.insert(startLeft + index - startRight, step)

    def AddStep(self, stepKey, step):
        """
        Instead of appending a step, this version will check the desired render step order
        and insert a named step in what it thinks is the correct order.
        If a step already exists, it is replaced
        If the renderJob is a multiview stage, check if the step is valid for this stage, if so add it
        """
        
        # Render order may be different if we're doing a multi-view rendering setup
        renderStepOrder = self.GetRenderStepOrderList()
        
        # Invalid multi-step stage setting
        if renderStepOrder is None:
            return None

        # Key is not valid for this mode of rendering
        if stepKey not in renderStepOrder:
            return None
                                
        # Step may exist already
        if stepKey in self.stepsLookup:
            s = self.stepsLookup[stepKey]
            if s.object is None:
                # step was deleted. Remove from dict and continue                
                del self.stepsLookup[stepKey]
            else:
                # Step exists. Replace it.
                replaceIdx = self.steps.index(s.object)
                if replaceIdx >= 0:
                    while True:
                        try:
                            self.steps.remove(s.object)
                        except:
                            break
                            
                    self.steps.insert(replaceIdx, step)
                    step.name = stepKey
                    self.stepsLookup[stepKey] = blue.BluePythonWeakRef(step)
                    self._AddStereoStep(step)
                    return step

        # Step does not exist already, unless a user inserted it manually
        # We don't deal with this edge case currently
        stepIdx = renderStepOrder.index(stepKey)
        nextExistingStepIdx = None
        nextExistingStep = None

        for i, oStep in enumerate(renderStepOrder[stepIdx+1:]):
            if oStep in self.stepsLookup and self.stepsLookup[oStep].object is not None:
                nextExistingStepIdx = i + stepIdx
                nextExistingStep = self.stepsLookup[oStep].object 
                break
        
        if nextExistingStepIdx is not None:
            insertPosition = self.steps.index(nextExistingStep)
            self.steps.insert(insertPosition, step)
            step.name = stepKey
            self.stepsLookup[ stepKey ] = blue.BluePythonWeakRef(step)            
            
            self._AddStereoStep(step)
            
            return step
        else:
            # use the dictionary key as the name
            step.name = stepKey
            self.stepsLookup[ stepKey ] = blue.BluePythonWeakRef(step)
            self.steps.append(step)
            self._AddStereoStep(step)
            # return the step in case anyone needs to do more setup
            return step

    def HasStep(self, stepKey):
        """
        Returns True iff the step is in the steps dictionary
        and the weakref has not died
        """
        if stepKey in self.stepsLookup:
            s = self.stepsLookup[ stepKey ].object
            if s is not None:
                return True
        return False

    def RemoveStep(self, stepKey):
        if stepKey in self.stepsLookup:
            s = self.stepsLookup[ stepKey ].object
            if s is not None:
                while True:
                    try:
                        self.steps.remove(s)
                    except:
                        break
            del self.stepsLookup[ stepKey ]

    def EnableStep(self, stepKey):
        """
        Enables a disabled step
        """
        self.SetStepAttr(stepKey, 'enabled', True)

    def DisableStep(self, stepKey):
        """
        Stops a step from running, without removing it
        """
        self.SetStepAttr(stepKey, 'enabled', False)

    def GetStep(self, stepKey):
        """
        Grab the weakreffed object for a step from the dictionary, if it exists
        """
        if stepKey in self.stepsLookup:
            return self.stepsLookup[ stepKey ].object
        return None

    def SetStepAttr(self, stepKey, attr, val):
        """
        Attempt to find a key in the dictionary, and if it exists and still has an object
        then set the given attribute name on it to the given value
        """
        if stepKey in self.stepsLookup:
            s = self.stepsLookup[ stepKey ].object
            if s is not None:
                setattr(s, attr, val)

    def GetScene(self):
        if self.scene is None:
            return None
        else:
            return self.scene.object

    def GetVisualizationsForRenderjob(self):
        return self.visualizations

    def AppendRenderStepToRenderStepOrder(self, renderStep):
        if renderStep not in self.renderStepOrder:
            self.renderStepOrder.append(renderStep)

    def ApplyVisualization(self, vis):
        """
        Applies a visualization class to the renderjob
        """
        if self.appliedVisualization is not None:
            self.appliedVisualization.RemoveVisualization(self)
            self.appliedVisualization = None
        
        if vis is not None:
            visInstance = vis()
            visInstance.ApplyVisualization(self)
            self.appliedVisualization = visInstance

    # Provide Implementations of the following functions in derived classes
    
    def ManualInit(self, name = "BaseSceneRenderJob"):
        """
        Decorated classes cannot use a normal init function, so this must be called manually.
        You must implement _ManualInit(...) on derived classes
        """
        self.name = name
        self.scene = None

        self.stepsLookup = {}
        self.enabled = False
        self.scheduled = False
        self.canCreateRenderTargets = True

        self.appliedVisualization = None
        self.currentMultiViewStageKey = None

        self.view = None
        self.projection = None
        self.viewport = None

        self.swapChain = None

        # Always default-initialize the name of the renderjob
        self._ManualInit(name)

    def DoPrepareResources(self):
        """
        This function is called when the device is restored. 
        This function may raise exceptions attempting to create resources!
        NB: Will need to be changed to allow other sources to provide the buffers
        """
        raise NotImplementedError("You must provide an implementation of DoPrepareResources(self)")

    def DoReleaseResources(self, level):
        """
        This function is called when the device is lost.
        """
        raise NotImplementedError("You must provide an implementation of DoReleaseResources(self, level)")

    def SetScene(self, scene):
        """
        Sets a scene into the render job. You must implement _SetScene(self, scene) on derived classes
        """
        if scene is None:
            self.scene = None
        else:
            self.scene = blue.BluePythonWeakRef(scene)

        self._SetScene(scene)

    def CreateBasicRenderSteps(self):
        """
        Creates a basic set of render steps. You must implement _CreateBasicRenderSteps(self) on derived classes
        """
        # Clear all the steps
        self.steps.removeAt(-1)
        self.stepsLookup = {}

        self._CreateBasicRenderSteps()

    def SetRenderTargetCreationEnabled(self, enabled):
        self.canCreateRenderTargets = enabled

        if enabled:
            try:
                self.DoPrepareResources()
            except trinity.D3DError:
                pass

    def SetMultiViewStage(self, stageKey):
        self.currentMultiViewStageKey = stageKey
        
        # Make sure to clear out any steps that do not match the stage key
        validStepList = self.GetRenderStepOrderList()

        if validStepList:
            for stepID in self.stepsLookup.keys():
                if stepID not in validStepList:
                    self.RemoveStep(stepID)

    def GetRenderTargets(self):
        """
        This function returns the a tuple of render targets that SetRenderTargets takes as a parameter
        """
        raise NotImplementedError("You must provide an implementation of GetRenderTargets(self)")

    def SetRenderTargets(self):
        """
        This function takes as a parameter the returned *tuple from GetRenderTargets
        """
        raise NotImplementedError("You must provide an implementation of SetRenderTargets(self, ...)")

    def SetViewport(self, viewport):
        """
        Sets the main viewport.
        """
        
        if viewport is None:
            self.RemoveStep("SET_VIEWPORT")
            self.viewport = None
        else:
            self.AddStep("SET_VIEWPORT", trinity.TriStepSetViewport(viewport))
            self.viewport = blue.BluePythonWeakRef(viewport)

    def GetViewport(self):
        """
        Gets the main viewport.
        """
        
        if self.viewport is None:
            return None

        if hasattr(self.viewport, 'object'):
            return self.viewport.object
        else:
            return self.viewport

    def SetCameraView(self, view):
        if view is None:
            self.RemoveStep("SET_VIEW")
            self.view = None
        else:
            self.AddStep("SET_VIEW", trinity.TriStepSetView(view))
            self.view = blue.BluePythonWeakRef(view)

    def SetCameraProjection(self, proj):
        if proj is None:
            self.RemoveStep("SET_PROJECTION")
            self.projection = None
        else:
            self.AddStep("SET_PROJECTION", trinity.TriStepSetProjection(proj))
            if self.stereoEnabled:
                self.originalProjection = blue.BluePythonWeakRef(proj)
            else:
                self.projection = blue.BluePythonWeakRef(proj)

    def GetCameraProjection(self):
        """
        Gets the projection matrix from the renderjob's camera.
        """
        
        if self.projection is None:
            return None

        if hasattr(self.projection, 'object'):
            return self.projection.object
        else:
            return self.projection

    def SetActiveCamera(self, camera):
        """
        This call adds or removes the steps nessecary for controlling the camera
        depending on if 'camera' is None
        """
        self.SetCameraView(camera.viewMatrix)
        self.SetCameraProjection(camera.projectionMatrix)

    def SetClearColor(self, color):
        """
        This call sets the clear color, if a CLEAR renderstep exists.
        """
        step = self.GetStep("CLEAR")
        if step is not None:
            step.color = color        
    
    def _StereoUpdateViewProjection(self, eye):
        """
        A TriStepPythonCB callback function to update projection matrix for the given eye
        (left or right).
        """
        if self.originalProjection.object.transform[2][3] != 0:
            offset = trinity.stereoSupport.GetEyeSeparation() * trinity.stereoSupport.GetSeparation()
            if eye == trinity.STEREO_EYE_LEFT:
                offset = -offset
            projection = (self.originalProjection.object.transform[0],
                          self.originalProjection.object.transform[1],
                          geo2.Vec4Add(self.originalProjection.object.transform[2], (-offset, 0, 0, 0)),
                          geo2.Vec4Add(self.originalProjection.object.transform[3], (-offset * trinity.stereoSupport.GetConvergence(), 0, 0, 0))
                         )

            self.projection.object.CustomProjection(projection)
            
            trinity.stereoSupport.SetActiveEye(eye)

    def EnableStereo(self, enable):
        """
        Enable/disable stereo rendering in this render job.
        """
        if enable == self.stereoEnabled:
            return True
            
        if enable:
            def leftCallback():
                return self._StereoUpdateViewProjection(trinity.STEREO_EYE_LEFT)
            
            def rightCallback():
                return self._StereoUpdateViewProjection(trinity.STEREO_EYE_RIGHT)
                
            leftUpdate = self.AddStep("UPDATE_STEREO", trinity.TriStepPythonCB())
            if leftUpdate is None:
                return False
            leftUpdate.SetCallback(leftCallback)

            self.originalProjection = self.projection
            self.stereoProjection = trinity.TriProjection()

            self.SetCameraProjection(self.stereoProjection)
            
            rightUpdate = trinity.TriStepPythonCB()
            rightUpdate.name = "UPDATE_STEREO_RIGHT"
            rightUpdate.SetCallback(rightCallback)
            self.steps.append(rightUpdate)
                
            index = -1
            try:
                index = self.steps.index(self.GetStep("UPDATE_STEREO"))
            except:
                pass
            if index >= 0:
                count = len(self.steps)
                for i in range(index + 1, count - 1):
                    step = self.steps[i]
                    self.steps.append(step)

            self.stereoEnabled = True
        else:
            index = -1
            for i, step in enumerate(self.steps):
                if step.name == "UPDATE_STEREO_RIGHT":
                    index = i
                    break
            if index >= 0:
                while len(self.steps) > index:
                    self.steps.removeAt(index)
                
            self.stereoEnabled = False

            self.RemoveStep("UPDATE_STEREO")

            self.SetCameraProjection(self.originalProjection.object)


        return True

    def SetSwapChain(self, swapChain):
        """
        Adds or removes a final present swapchain renderstep.
        """        
        self.DoReleaseResources(1)
        if swapChain is None:
            self.RemoveStep("PRESENT_SWAPCHAIN")
        else:
            self.AddStep("PRESENT_SWAPCHAIN", trinity.TriStepPresentSwapChain(swapChain))
        
        self.swapChain = blue.BluePythonWeakRef(swapChain)
        self.DoPrepareResources()

    def GetSwapChain(self):
        """
        Gets the SwapChain of the renderjob
        """     
        if self.swapChain is not None:
            return self.swapChain.object   
        
        return None

    def GetBackBufferSize(self):
        """
        Gets the size of the BackBuffer of the renderjob
        """
        if self.GetSwapChain() is not None:
            # Sometimes the backbuffer has not been initialized, but the width and height
            # of the swapchain is always there
            width = self.GetSwapChain().width
            height = self.GetSwapChain().height
        else:    
            width = _singletons.device.GetPresentParameters()['BackBufferWidth']
            height = _singletons.device.GetPresentParameters()['BackBufferHeight']

        return width, height

    def GetBackBufferRenderTarget(self):
        """
        Gets the BackBufferRenderTarget based on the renderContext or swapchain
        """
        if self.GetSwapChain() is not None:
            return self.GetSwapChain().backBuffer
        
        return _singletons.device.GetRenderContext().GetDefaultBackBuffer()

    def GetDepthStencilWithRTMAL(self, depthFormat, backBufferDepthStencil, renderTargetIndex):
        """
        Gets the BackBufferDepthStencil. If it is None it gets created with the renderTargetManager
        """
        if backBufferDepthStencil is not None and depthFormat == backBufferDepthStencil.format:
            return backBufferDepthStencil
        else :
            width, height = self.GetBackBufferSize()
            result = rtm.GetDepthStencilAL(
                width, height, 
                depthFormat, 
                index = renderTargetIndex)
            if result is not None:
                result.name = 'depthStencil'
            return result
