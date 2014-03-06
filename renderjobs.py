import decometaclass
from . import _trinity as trinity


class RenderJobs(object):
    __cid__ = "trinity.Tr2RenderJobs"
    __metaclass__ = decometaclass.BlueWrappedMetaclass

    def __init__(self):
        pass
        
    def UnscheduleByName(self, name):
        """
        Case sensitive search for a renderJob that's scheduled recurring with this name,
        and unschedules it.  Returns False if not found.
        """
        for rj in self.recurring:
            if rj.name == name:
                self.recurring.remove(rj)
                return True
        return False

    def FindByName(self, name):
        """
        Case sensitive search for a renderJob that's scheduled recurring with this name,
        returns None if not found.
        """
        for rj in self.recurring:
            if rj.name == name:
                return rj
        return None

    def FindStepByName(self, name):
        """
        Case sensitive search for a renderJob that's scheduled recurring with this name,
        returns None if not found.
        """
        def FindInJob(rj):
            for step in rj.steps:
                if step.name == name:
                    return step
        for rj in self.recurring:
            ret = FindInJob(rj)
            if ret is not None:
                return ret
        return None

    def FindScenes(self, sceneType, filter = lambda x: True):
        """
        Recursively walk all scheduled renderjobs, and any nested jobs (through TriStepRunJob),
        finding any 'object' members on any TriStep whose type matches sceneType and for which
        the filter method returns True.
        Returns a set with all the scenes that were found matching the type and filter.
        """
        results = set({})

        def RecursiveSearch(job):
            for step in job.steps:
                if hasattr(step, "object") and type( step.object ) is sceneType and filter(step.object):
                    results.add(step.object)
                    return
                elif type(step) is trinity.TriStepRunJob:
                    RecursiveSearch(step.job)

        for job in self.recurring:
            RecursiveSearch(job)
        return results