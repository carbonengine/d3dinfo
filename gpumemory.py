from nicenum import FormatMemory
import trinity


class ResourceFilters(object):
    """
    Helper methods for live AL resource filtering. All methods accept AL type name and resource description dict.
    """

    @staticmethod
    def IsTexture(name, _):
        return name == 'Tr2TextureAL'

    @staticmethod
    def IsRenderTarget(name, value):
        return name == 'Tr2TextureAL' and (int(value.get('gpuUsage', 0)) & (1 << 2)) != 0

    @staticmethod
    def IsDepthStencil(name, value):
        return name == 'Tr2TextureAL' and (int(value.get('gpuUsage', 0)) & (1 << 3)) != 0

    @staticmethod
    def IsImmutable(_, value):
        return (int(value.get('gpuUsage', 0)) & ((1 << 2) | (1 << 3) | (1 << 5) | (1 << 6))) == 0 and \
               (int(value.get('cpuUsage', 0)) & (1 << 1)) == 0

    @staticmethod
    def IsBuffer(name, _):
        return name == 'Tr2BufferAL'

    @staticmethod
    def IsDynamic(_, value):
        return (int(value.get('cpuUsage', 0)) & (1 << 3)) != 0


_COLUMN_ORDER = [
    'size',
    'texType',
    'width',
    'height',
    'depth',
    'mipLevels',
    'format']


def GetResourceListColumns(resources):
    """
    Returns ordered list of column names (keys into resource description dict) for a live AL resource list.

    :param resources: per-type list of AL resource data
    :type resources: list[dict[str, str]]
    :rtype: list[str]
    """
    keys = set()
    for item in resources:
        for key in item:
            keys.add(key)
    if 'type' in keys and len(keys) > 1:
        keys.remove('type')

    def keyCmp(x, y):
        try:
            i0 = _COLUMN_ORDER.index(x)
        except ValueError:
            i0 = None
        try:
            i1 = _COLUMN_ORDER.index(y)
        except ValueError:
            i1 = None
        if i0 is not None and i1 is not None:
            return cmp(i0, i1)
        if i0 is not None and i1 is None:
            return -1
        if i0 is None and i1 is not None:
            return 1
        return cmp(x, y)

    return sorted(keys, cmp=keyCmp)


def FormatCpuUsage(value):
    """
    Returns string representation for "cpuUsage" bitfield
    :param value: cpuUsage bitfield
    :type value: int
    """
    if value == 0:
        return 'None'
    result = []
    READ = 1 << 0
    WRITE = 1 << 1
    READ_OFTEN = READ | (1 << 2)
    WRITE_OFTEN = WRITE | (1 << 3)
    if (value & WRITE_OFTEN) == WRITE_OFTEN:
        result.append('WriteOften')
    elif (value & WRITE) == WRITE:
        result.append('Write')
    if (value & READ_OFTEN) == READ_OFTEN:
        result.append('ReadOften')
    elif (value & READ) == READ:
        result.append('Read')
    return ' '.join(result)


_GPU_USAGE = ((1 << 0, 'VB'), (1 << 1, 'IB'), (1 << 2, 'RT'), (1 << 3, 'DS'),
              (1 << 4, 'SRV'), (1 << 5, 'UAV'), (1 << 6, 'CopyDest'), (1 << 7, 'IndirectArgs'), (1 << 9, 'Shared'))


def FormatGpuUsage(value):
    """
    Returns string representation for "gpuUsage" bitfield
    :param value: gpuUsage bitfield
    :type value: int
    """
    if value == 0:
        return 'None'
    return ' '.join(v for k, v in _GPU_USAGE if ((k & value) == k))


def FormatField(key, value):
    """
    For a given field named key in the AL resource description, returns its string representation and sorting value
    :param key: resource description key
    :param value: resource description value
    :return: sorting value, string representation
    """
    if key == "format":
        # noinspection PyCallByClass,PyTypeChecker
        value = trinity.PIXEL_FORMAT.GetNameFromValue(int(value))
        return value, value
    elif key == 'texType':
        return int(value), {1: '1D', 2: '2D', 3: '3D', 4: 'Cube'}.get(int(value), value)
    elif key == 'cpuUsage':
        return int(value), FormatCpuUsage(int(value))
    elif key == 'gpuUsage':
        return int(value), FormatGpuUsage(int(value))
    elif key == "size":
        return int(value), FormatMemory(int(value))
    try:
        return int(value), value
    except ValueError:
        return value, value


def GetResourceRow(resource, columns):
    row = ['' for _ in range(len(columns))]
    """:type: list[any]"""
    for item in resource:
        value = resource[item]
        if item not in columns:
            continue
        col = columns[item]
        row[col] = FormatField(item, value)
    return tuple(row)
