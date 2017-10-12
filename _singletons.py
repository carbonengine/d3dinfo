"""
This is where we initialize singletons that are accessible at module root level.
e.g. trinity.SingletonName
"""
import logging

import blue

# Load the Trinity DLL and then we create a reference to the newly
# created Trinity Device and store it as a module global variable.
# This only gets evaluated once, and is the preferred way of accessing
# the Trinity Device in Python Code
from . import _trinity
platform = _trinity._ImportDll()
adapters = _trinity._blue.classes.CreateInstance("trinity.Tr2VideoAdapters")
device = _trinity._blue.classes.CreateInstance("trinity.TriDevice")
app = _trinity._blue.classes.CreateInstance("triui.App")

# Our singleton which goes on the device.
from . import renderjobs
renderJobs = renderjobs.RenderJobs()

from . import GraphManager
graphs = GraphManager.GraphManager()


def _ReportRemovedDevice(hr, message, count, marker, pageFaultResource):
    logging.error('GPU device removed',
                  extra={"count": count, "error_message": message, "pageFaultResource": pageFaultResource,
                         "tags": {"reason": '0x%x' % hr, "marker": marker}})

device.onDeviceRemoved = _ReportRemovedDevice