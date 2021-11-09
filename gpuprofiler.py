import locale
import weakref

import blue
import trinity


def _FormatGpuTime(time):
    if time == 0:
        return '0'
    elif time > 1:
        return '%.1fs' % time
    elif time > 0.001:
        return '%.1fms' % (time * 1000)
    else:
        return '%.1f\xb5s' % (time * 1000000)


def _ToString(name, value):
    if name == 'GPU Time':
        return _FormatGpuTime(value)
    if isinstance(value, (int, long)):
        return locale.format('%d', value, grouping=True)
    return str(value)


class Tr2GpuProfilerIndexes(object):
    """
    Names for tuple fields returned by Tr2Profiler.GetFrameReport
    """
    OWNER = 0
    MESSAGE = 1
    STATS = 2
    CHILDREN = 3


class RawZone(object):
    def __init__(self, data, order=None):
        """
        A simple wrapper for tuples returned by Tr2Profiler.GetFrameReport
        :param data: a tuple returned by Tr2Profiler.GetFrameReport
        :type data: (None|blue.IRoot, str, dict, tuple)
        """
        self.owner = data[Tr2GpuProfilerIndexes.OWNER]
        self.message = data[Tr2GpuProfilerIndexes.MESSAGE]
        self.stats = data[Tr2GpuProfilerIndexes.STATS]
        if order is None:
            self.order = 1
            order = [2]
        else:
            self.order = order[0]
            order[0] += 1
        self.children = [RawZone(x, order) for x in data[Tr2GpuProfilerIndexes.CHILDREN]]


class BaseProfileNode(object):
    def __init__(self):
        self.owner = None
        self.name = ''
        self.stats = {}
        self.statText = {}
        self.parent = None
        self.children = []

    def AddChild(self, child):
        self.children.append(child)
        child.parent = weakref.ref(self)

    def AggregateResults(self):
        for each in self.children:
            each.AggregateResults()

        if not self.stats:
            for each in self.children:
                for k, v in each.stats.items():
                    self.stats[k] = self.stats.get(k, 0L) + v
            self._PopulateStatText()

    def GetOrder(self):
        return ''

    def _PopulateStatText(self):
        self.statText = {k: _ToString(k, v) for k, v in self.stats.items()}


def _GetZoneName(zone):
    if isinstance(zone.owner, trinity.Tr2Effect) and zone.owner.effectResource:
        return zone.owner.effectResource.path.rsplit('/', 1)[-1]
    elif getattr(zone.owner, 'name', ''):
        return '%s %s' % (type(zone.owner).__name__, zone.owner.name)
    elif zone.owner is None:
        return zone.message or 'Unnamed'
    else:
        return type(zone.owner).__name__


class ZoneNode(BaseProfileNode):
    def __init__(self, item):
        """
        Object to represent a zone in profiler view
        :param item: zone data
        :type item: RawZone
        """
        super(ZoneNode, self).__init__()
        self.zone = item
        self.owner = item.owner
        self.name = _GetZoneName(item)
        self.stats = item.stats
        self._PopulateStatText()

    def GetOrder(self):
        return self.zone.order


class ObjectReferenceNode(BaseProfileNode):
    def __init__(self, obj, label):
        """
        Object to represent a blue object reference in profiler view
        :param obj: blue object that owns nested zones
        :type obj: None|blue.IRoot
        :param label: label for the node
        :type label: str
        """
        super(ObjectReferenceNode, self).__init__()
        self.owner = obj
        self.name = label


def GetStatKeys(node):
    """
    Returns names of the first non-empty stats dictionary in the profiler node tree
    :param node: root node
    :type node: BaseProfileNode
    """
    if node.stats:
        return node.stats.keys()
    for each in node.children:
        r = GetStatKeys(each)
        if r:
            return r
    return []


def BuildZoneTree(item):
    """
    Builds a tree of zone nodes
    :param item: root RawZone node
    :type item: RawZone
    """
    zone = ZoneNode(item)
    for each in item.children:
        zone.AddChild(BuildZoneTree(each))
    return zone


def _RecordRoute(start, route, label):
    if not route:
        return start
    first = route[0]
    for each in start.children:
        if each.owner == first[0]:
            return _RecordRoute(each, route[1:], first[2] if first[1] == 0 else '')
    if not label:
        label = getattr(first[0], 'name', '') or type(first[0]).__name__
    node = ObjectReferenceNode(first[0], label)
    node.parent = start
    start.AddChild(node)
    return _RecordRoute(node, route[1:], first[2] if first[1] == 0 else '')


def _PopulateObjectTree(root, scenes, node, orphans):
    owner = node.owner
    parent = None
    if owner:
        for each in scenes:
            routes = blue.FindRoute(each, owner)
            if routes:
                parent = _RecordRoute(root, routes[0] + [(owner, 0, '')], '')
                break
    if parent:
        parent.AddChild(ZoneNode(node))
    elif not node.children:
        if not orphans:
            orphans.append(ObjectReferenceNode(None, 'Orphans'))
        orphans[0].AddChild(ZoneNode(node))
    for each in node.children:
        _PopulateObjectTree(root, scenes, each, orphans)


def BuildObjectTree(zones, scenes):
    """
    Builds owner object tree for the profiler zones
    :param zones: root RawZone node
    :type zones: RawZone
    :param scenes: list of top-level blue objects (scenes or render jobs)
    :type scenes: list[blue.IRoot]
    """
    orphans = []
    root = ZoneNode(zones)
    _PopulateObjectTree(root, scenes, zones, orphans)
    if orphans:
        root.AddChild(orphans[0])
    return root
