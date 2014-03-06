import decometaclass
import blue

from . import _trinity as trinity
from ._singletons import renderJobs


class RenderJob(object):
    __cid__ = "trinity.TriRenderJob"
    __metaclass__ = decometaclass.BlueWrappedMetaclass

    def __init__(self):
        self.cancelled = False

    def ScheduleOnce(self):
        """
        Add this job to the device's list of jobs to run once
        """
        self.status = trinity.RJ_INIT
        renderJobs.once.append(self)

    def ScheduleChained(self):
        """
        Add this job to the device's list of jobs to run once
        """
        renderJobs.chained.append(self)

    def CancelChained(self):
        """
        Cancel this render job
        """
        self.cancelled = True
        if self in renderJobs.chained:
            renderJobs.chained.remove(self)

    def ScheduleRecurring(self, scheduledRecurring=None, insertFront=False):
        """
        Add this job to the given list of render jobs. If no list is given,
        add this job to the device's scheduledRecurring list.
        """
        if scheduledRecurring is None:
            scheduledRecurring = renderJobs.recurring

        if insertFront == False:
            scheduledRecurring.append(self)
        else:
            scheduledRecurring.insert(0, self)

    def ScheduleUpdate(self, scheduledUpdate=None, insertFront=False):
        """
        Add this job to the given list of render jobs. If no list is given,
        add this job to the device's updateRecurring list.
        """
        self.ScheduleRecurring(renderJobs.updateRecurring if scheduledUpdate is None else scheduledUpdate, insertFront)

    def UnscheduleRecurring(self, scheduledRecurring=None):
        """
        Remove this job from the given list of render jobs. If no list is given,
        remove this job from the device's scheduledRecurring list.
        """
        if scheduledRecurring is None:
            scheduledRecurring = renderJobs.recurring

        if self in scheduledRecurring:
            scheduledRecurring.remove(self)

    def UnscheduleUpdate(self, scheduledUpdate=None):
        """
        Remove this job from the given list of render jobs. If no list is given,
        remove this job from the device's updateRecurring list.
        """
        self.UnscheduleRecurring(renderJobs.updateRecurring if scheduledUpdate is None else scheduledUpdate)

    def WaitForFinish(self):
        """
        Block until this job has finished.
        """
        while not ((self.status == trinity.RJ_DONE) or (self.status == trinity.RJ_FAILED) or self.cancelled):
            blue.synchro.Yield()


def _GetRenderJobCreationClosure( functionName, doc, classThunker ):
    def CreateStep( self, *args ):
        step = classThunker( *args )
        self.steps.append( step )
        return step
    
    CreateStep.__doc__ = doc
    CreateStep.__name__ = functionName
    return CreateStep


def CreateRenderJob(name=None):
    job = RenderJob()
    if name:
        job.name = name
    return job


def _InitTriStep():
    for className, desc in trinity.GetClassInfo().iteritems():
        if className.startswith("TriStep"):
            setattr(RenderJob, className[7:], _GetRenderJobCreationClosure(
                                                    className[7:],
                                                    desc[3].get('__init__',"Create a %s render step and add it to the render job" % className),
                                                    getattr(trinity, className)
                                                    ))

_InitTriStep()