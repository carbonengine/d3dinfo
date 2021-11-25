from .sceneRenderJobSpace import SceneRenderJobSpace
from .renderJob import renderJobs

def CreateSceneRenderJobSpaceTransition(name=None):
    """
    We can't use __init__ on a decorated class, so we provide a creation function that does it for us
    """
    newRJ = SceneRenderJobSpaceTransition()
    if name is not None:
        newRJ.ManualInit(name)
    else:
        newRJ.ManualInit()
    return newRJ


class SceneRenderJobSpaceTransition(SceneRenderJobSpace):
    pass

    def Start(self):
        """
        Schedule the renderjob to run
        """
        self.renderOrder = 1
        super(SceneRenderJobSpaceTransition, self).Start()
        self.EnableGpuEmission(True)
        self.ScheduleUpdateJob()