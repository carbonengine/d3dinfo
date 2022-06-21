"""
This is where we initialize singletons that are accessible at module root level.
e.g. trinity.SingletonName
"""
import blue

# Load the Trinity DLL and then we create a reference to the newly
# created Trinity Device and store it as a module global variable.
# This only gets evaluated once, and is the preferred way of accessing
# the Trinity Device in Python Code
from . import _trinity
platform = _trinity._ImportDll()
adapters = _trinity._blue.classes.CreateInstance("trinity.Tr2VideoAdapters")
""":type: trinity.Tr2VideoAdapters"""
device = _trinity._blue.classes.CreateInstance("trinity.TriDevice")
""":type: trinity.TriDevice"""
mainWindow = _trinity._blue.classes.CreateInstance("trinity.Tr2MainWindow")
""":type: trinity.Tr2MainWindow"""
app = mainWindow
platformInfo = _trinity._blue.classes.CreateInstance("trinity.Tr2PlatformInfo")
""":type: trinity.Tr2PlatformInfo"""


# Our singleton which goes on the device.
from . import renderjobs
renderJobs = renderjobs.RenderJobs()

from . import GraphManager
graphs = GraphManager.GraphManager()


def _ReportRemovedDevice(hr, message, count, marker, pageFaultResource, offendingShader):
    import monolithsentry
    # sentry has a tag value length limitation to 200 chars, so lets truncate the shader from the beginning,
    # because the meat is in the end
    # https://docs.sentry.io/platforms/python/guides/logging/enriching-events/tags/
    if len(offendingShader) > 200:
        offendingShader = "..." + offendingShader[len(offendingShader) - 197:]

    monolithsentry.capture_error("GPU device removed",
                                 extra={"count": count, "error_message": message,
                                        "pageFaultResource": pageFaultResource},
                                 new_tags={"reason": '0x%x' % hr, "marker": marker, "offendingShader": offendingShader})

device.onDeviceRemoved = _ReportRemovedDevice
