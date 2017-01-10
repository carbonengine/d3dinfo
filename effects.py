import blue
import trinity
from shadercompiler import effectinfo


def GetPublicParameters(effect):
    """
    Returns all public parameters (those that have 'SasUiVisible' annotation) for compiled effect
    :param effect: effect object
    :type effect: trinity.Tr2Effect
    :rtype: dict[str, shadercompiler.effectinfo._Parameter]
    """
    path = blue.paths.ResolvePath(effect.effectFilePath)
    params, resources, _ = effectinfo.get_merged_parameters(path)
    return {name: param for name, param in params.items() if param.annotation.get('SasUiVisible', False)}


def GetPublicResources(effect):
    """
    Returns all public resources (those that have 'SasUiVisible' annotation) for compiled effect
    :param effect: effect object
    :type effect: trinity.Tr2Effect
    :rtype: dict[str, shadercompiler.effectinfo._Parameter]
    """
    path = blue.paths.ResolvePath(effect.effectFilePath)
    params, resources, _ = effectinfo.get_merged_parameters(path)
    return {name: param for name, param in resources.items() if param.annotation.get('SasUiVisible', False)}


def GetSamplers(effect):
    """
    Returns all samplers for compiled effect

    :param effect: effect object
    :type effect: trinity.Tr2Effect
    :rtype: dict[str, shadercompiler.effectinfo.Sampler]
    """
    path = blue.paths.ResolvePath(effect.effectFilePath)
    return effectinfo.get_merged_parameters(path)[2]


def PopulateParameters(effect):
    """
    Populate missing parameters for the effect

    :param effect: effect object
    :type effect: trinity.Tr2Effect
    """
    path = blue.paths.ResolvePath(effect.effectFilePath)
    params, resources, _ = effectinfo.get_merged_parameters(path)
    existing = set()
    for name, _ in effect.constParameters:
        existing.add(name)
    for param in effect.parameters:
        existing.add(param.name)
    for param in effect.resources:
        existing.add(param.name)
    for name, param in params.items():
        if name in existing:
            continue
        if not param.annotation.get('SasUiVisible', False):
            continue
        new = getattr(trinity, param.trinity_type)()
        new.name = name
        if param.constant.default_value is not None:
            new.value = param.constant.default_value
        effect.parameters.append(new)
    for name, param in resources.items():
        if name in existing:
            continue
        new = getattr(trinity, param.trinity_type)()
        effect.resources.append(new)


def PruneParameters(effect):
    """
    Removes unused parameters from the effect

    :param effect: effect object
    :type effect: trinity.Tr2Effect
    """
    path = blue.paths.ResolvePath(effect.effectFilePath)
    params, resources, _ = effectinfo.get_merged_parameters(path)
    params.update(resources)
    params = set([name for name, param in params if param.annotation.get('SasUiVisible', False)])
    delete = []
    for i, param in enumerate(effect.constParameters):
        if param[0] not in params:
            delete.append(i)
    for idx in reversed(delete):
        del effect.constParameters[idx]
    delete = []
    for i, param in enumerate(effect.parameters):
        if param.name not in params:
            delete.append(i)
    for idx in reversed(delete):
        del effect.parameters[idx]
    delete = []
    for i, param in enumerate(effect.resources):
        if param.name not in params:
            delete.append(i)
    for idx in reversed(delete):
        del effect.resources[idx]


def GetUnusedParameters(effect):
    """
    Returns a list of parameter names that are not used by the effect

    :param effect: effect object
    :type effect: trinity.Tr2Effect
    :rtype: list[str]
    """
    path = blue.paths.ResolvePath(effect.effectFilePath)
    params, resources, _ = effectinfo.get_merged_parameters(path)
    params.update(resources)
    result = []
    for name, _ in effect.constParameters:
        if name not in params:
            result.append(name)
    for param in effect.parameters:
        if param.name not in params:
            result.append(param.name)
    for param in effect.resources:
        if param.name not in params:
            result.append(param.name)
    return result


def GetMissingParameters(effect):
    """
    Returns a list of parameter names that are missing from the effect

    :param effect: effect object
    :type effect: trinity.Tr2Effect
    :rtype: list[str]
    """
    path = blue.paths.ResolvePath(effect.effectFilePath)
    params, resources, _ = effectinfo.get_merged_parameters(path)
    params.update(resources)
    existing = {name for name, _ in effect.constParameters}
    existing.update((p.name for p in effect.parameters))
    existing.update((p.name for p in effect.resources))
    return list(set(params.keys()).difference(existing))


def IsParameterUsed(effect, name):
    """
    Checks if the given parameter name is used by any permutation of the effect

    :param effect: effect object
    :type effect: trinity.Tr2Effect
    :param name: parameter name
    :type name: str
    :rtype: bool
    """
    path = blue.paths.ResolvePath(effect.effectFilePath)
    params, resources, _ = effectinfo.get_merged_parameters(path)
    return name in params or name in resources


def ConstToParameter(effect, name):
    """
    Moves the parameter with the specified name from constParameters to parameters list.

    :param effect: effect object
    :type effect: trinity.Tr2Effect
    :param name: parameter name
    :type name: str
    :raises ValueError: if the parameter name is invalid
    """
    path = blue.paths.ResolvePath(effect.effectFilePath)
    params, resources, _ = effectinfo.get_merged_parameters(path)
    if name not in params:
        raise ValueError('parameter \"%s\" is not used by the effect' % name)
    for i, p in enumerate(effect.constParameters):
        if p[0] == name:
            param = getattr(trinity, params[name].trinity_type)()
            param.name = p[0]
            if isinstance(param.value, float):
                param.value = p[1][0]
            else:
                param.value = p[1][:len(param.value)]
            effect.parameters.append(param)
            del effect.constParameters[i]
            return
    raise ValueError('parameter \"%s\" is not found in constParameters' % name)


def ParameterToConst(effect, name):
    """
    Moves the parameter with the specified name from parameters to constParameters list.

    :param effect: effect object
    :type effect: trinity.Tr2Effect
    :param name: parameter name
    :type name: str
    :raises ValueError: if the parameter name is invalid
    """
    p = effect.parameters.FindByName(name)
    if not p:
        raise ValueError('parameter \"%s\" is not found in parameters' % name)
    if not isinstance(p.value, (float, tuple)):
        raise ValueError('don\'t know how to handle parameter type %s' % type(p))
    if isinstance(p.value, tuple):
        if len(p.value) > 4 or not isinstance(p.value[0], float):
            raise ValueError('don\'t know how to handle parameter type %s' % type(p))
        v = p.value + (0.0,) * (4 - len(p.value))
    else:
        v = p.value, 0.0, 0.0, 0.0
    effect.constParameters.append((name, v))
    effect.parameters.remove(p)


class _VectorWrapper(object):
    def __init__(self, value):
        self._value = value

    def __getitem__(self, item):
        return self._value[item]

    def __getattr__(self, item):
        result = []
        for each in item:
            if each in ('r', 'x'):
                result.append(self._value[0])
            elif each in ('g', 'y'):
                result.append(self._value[1])
            elif each in ('b', 'z'):
                result.append(self._value[2])
            elif each in ('a', 'w'):
                result.append(self._value[3])
            else:
                raise AttributeError(item)
        return tuple(result)


class _MatrixWrapper(object):
    def __init__(self, value):
        self._value = value

    def __getitem__(self, item):
        return self._value[item]

    def __getattr__(self, item):
        if len(item) == 3 and item[0] == '_' and item[1] in '1234' and item[3] in '1234':
            row = ord(item[1]) - ord('1')
            col = ord(item[2]) - ord('1')
            return self._value[row][col]
        raise AttributeError(item)


def _WrapParameterValue(value, param):
    if param.constant.elements > 1:
        return []
    elif param.constant.dimension == 16:
        return _MatrixWrapper(value)
    elif param.constant.dimension == 1:
        if isinstance(value, tuple):
            return value[0]
        return value
    else:
        return _VectorWrapper(value)


def ValidateParameterValue(effect, name, value):
    """
    Moves the parameter with the specified name from parameters to constParameters list.

    :param effect: effect object
    :type effect: trinity.Tr2Effect
    :param name: parameter name
    :type name: str
    :raises ValueError: if parameter with the specified name is not in the compiled effect
    :raises AssertionError: if validation fails
    """
    path = blue.paths.ResolvePath(effect.effectFilePath)
    params, resources, _ = effectinfo.get_merged_parameters(path)
    if name not in params:
        raise ValueError('parameter %s not found in the effect resource' % name)
    validation = params[name].annotation.get('Validation', '')
    if not validation:
        return
    p = {}
    for n, v in effect.constParameters:
        if n in params:
            p[n] = _WrapParameterValue(v, params[n])
    for each in effect.parameters:
        if each.name in params:
            p[each.name] = _WrapParameterValue(each.value, params[each.name])
    p['self'] = _WrapParameterValue(value, params[name])
    if not eval(validation, {}, p):
        raise AssertionError(params[name].annotation.get('ValidationMessage', 'invalid value'))
