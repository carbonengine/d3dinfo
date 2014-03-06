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
device = _trinity._blue.classes.CreateInstance("trinity.TriDevice")
app = _trinity._blue.classes.CreateInstance("triui.App")
shaderManager = _trinity.GetShaderManager()

# Our singleton which goes on the device.
from . import renderjobs
renderJobs = renderjobs.RenderJobs()

from . import GraphManager
graphs = GraphManager.GraphManager()