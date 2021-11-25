from . import _trinity
from . import _singletons
import blue as _blue


class RenderTargetManager(object):
    """ 
        Designed to manage render targets used by render jobs so they can be 
        shared between render jobs.
    """

    def __init__(self):
        self.targets = {}

    def _Get(self, key, function, *args):
        """
            Returns a render target created by the function argument
            using args as arguments for the function.
        """
        if key in self.targets and self.targets[key].object is not None:
            rt = self.targets[key].object
            if not rt.isValid:
                function(*args, target=rt)
            return rt

        def DeleteObject():
            self.targets.pop(key)

        rt = function(*args)
        self.targets[key] = _blue.BluePythonWeakRef(rt)
        self.targets[key].callback = DeleteObject
        return rt

    #TODO now that the legacy code is dead, rename these fooAL back to foo

    @staticmethod
    def _CreateDepthStencilAL(width, height, format, msaaType, msaaQuality, target=None):
        if target is None:
            target = _trinity.Tr2DepthStencil()
        target.Create(width, height, format, msaaType, msaaQuality)
        return target

    def GetDepthStencilAL(self, width, height, format, msaaType=1, msaaQuality=0, index=0):
        """
            Returns a new AL-style Tr2DepthStencil.
            index is used to uniquely identify depthStencils.
        """        
        key = (RenderTargetManager._CreateDepthStencilAL, index, width, height, format, msaaType, msaaQuality)
        return self._Get(key, RenderTargetManager._CreateDepthStencilAL, width, height, format, msaaType, msaaQuality)

    @staticmethod
    def _CreateRenderTargetAL(width, height, mipLevels, format, target=None):
        if target is None:
            target = _trinity.Tr2RenderTarget()
        target.Create(width, height, mipLevels, format)
        return target

    @staticmethod
    def _CreateRenderTargetMsaaAL(width, height, format, msaaType, msaaQuality, target=None):
        if target is None:
            target = _trinity.Tr2RenderTarget()
        target.Create(width, height, 1, format, msaaType, msaaQuality)
        return target

    def GetRenderTargetAL(self, width, height, mipLevels, format, index=0):
        """
            Returns a new AL-style Tr2RenderTarget.
            index is used to uniquely identify renderTargets.
        """        
        key = (RenderTargetManager._CreateRenderTargetAL, index, width, height, mipLevels, format)
        return self._Get(key, RenderTargetManager._CreateRenderTargetAL, width, height, mipLevels, format)

    def GetRenderTargetMsaaAL(self, width, height, format, msaaType, msaaQuality, index=0):
        """
            Returns a new AL-style Tr2RenderTarget with MSAA.
            index is used to uniquely identify renderTargets.
        """        
        key = (RenderTargetManager._CreateRenderTargetMsaaAL, index, width, height, format, msaaType, msaaQuality)
        return self._Get(key, RenderTargetManager._CreateRenderTargetMsaaAL, width, height, format, msaaType, msaaQuality)
            

    def CheckRenderTarget(self, target, width, height, format):
        """
            Compares the render target width, height and format with the parameters provided.
            Returns True if they all match, False otherwise.
        """
        return target.width == width and target.height == height and target.format == format


renderTargetManager = RenderTargetManager()