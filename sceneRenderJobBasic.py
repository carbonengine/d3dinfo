from . import _trinity as trinity
from .sceneRenderJobBase import SceneRenderJobBase


def CreateSceneRenderJobBasic( name = None ):
    """
    We can't use __init__ on a decorated class, so we provide a creation function that 
    does it for us
    """
    newRJ = SceneRenderJobBasic()
    if name is not None:
        newRJ.ManualInit(name)
    else:
        newRJ.ManualInit()
    return newRJ


class SceneRenderJobBasic( SceneRenderJobBase ):

    # This is a master list that we can refer to, when we want to insert steps that are 
    # not already in the render steps, by looking for the prior or next step that exists, 
    # in order to position the new one
    # See: AddStep
    renderStepOrder = [
        "UPDATE_SCENE",
        "SET_VIEWPORT",
        "SET_PROJECTION",
        "SET_VIEW",
        "SET_RENDERTARGET",
        "SET_DEPTH",
        "CLEAR",
        "RENDER_SCENE",
        "UPDATE_TOOLS", 
        "RENDER_PROXY", 
        "RENDER_INFO",
        "RENDER_VISUAL",
        "RENDER_TOOLS", 
        "RESTORE_DEPTH",
        "RESTORE_RENDERTARGET", 
        "PRESENT_SWAPCHAIN"
    ]

    def _ManualInit(self, name = "SceneRenderJobInterior"):
        """
        Decorated classes cannot use a normal init function, so this must be called 
        manually.  This version is called from ManualInit on SceneRenderJobBase.
        """
        # in general most of these use weakrefs to prevent circular references
        self.ui = None

    def _SetScene( self, scene ):
        """
        Sets a scene into the render job
        """
        self.SetStepAttr( "UPDATE_SCENE", 'object', scene )
        self.SetStepAttr( "RENDER_SCENE", 'scene', scene )

    def _CreateBasicRenderSteps( self ):
        # This will clear the current steps
        # Create approximately the most basic renderjob setup
        self.AddStep( "UPDATE_SCENE", trinity.TriStepUpdate( self.GetScene() ) )
        self.AddStep( "RENDER_SCENE", trinity.TriStepRenderScene( self.GetScene() ) )

    def DoReleaseResources(self, level):
        """
        This function is called when the device is lost.
        """
        pass      

    def DoPrepareResources(self):
        """
        This function is called when the device is restored. 
        This function may raise exceptions attempting to create resources!
        """
        if self.GetSwapChain():
            self.AddStep("SET_RENDERTARGET", trinity.TriStepPushRenderTarget(self.GetSwapChain().backBuffer))
            self.AddStep("SET_DEPTH", trinity.TriStepPushDepthStencil(self.GetSwapChain().depthStencilBuffer))
            self.AddStep("RESTORE_RENDERTARGET", trinity.TriStepPopRenderTarget())
            self.AddStep("RESTORE_DEPTH", trinity.TriStepPopDepthStencil())
            if not self.HasStep('CLEAR'):
                self.AddStep("CLEAR", trinity.TriStepClear((0.0, 0.0, 0.0, 0.0), 1.0))
        else:
            self.RemoveStep("SET_RENDERTARGET")
            self.RemoveStep("SET_DEPTH")
            self.RemoveStep("RESTORE_RENDERTARGET")
            self.RemoveStep("RESTORE_DEPTH")

    def SetUI( self, ui ):
        """
        This call adds or removes the steps nessecary for rendering the UI
        depending on if 'ui' is None
        """
        if ui is None:
            self.RemoveStep("UPDATE_UI")
            self.RemoveStep("RENDER_UI")
        else:
            self.AddStep("UPDATE_UI", trinity.TriStepUpdate(ui) )
            self.AddStep("RENDER_UI", trinity.TriStepRenderUI(ui) )

    def EnableSceneUpdate( self, isEnabled ):
        if isEnabled:
            self.AddStep( "UPDATE_SCENE", trinity.TriStepUpdate( self.GetScene() ) )
        else:
            self.RemoveStep("UPDATE_SCENE")
