import ast

import blue
import trinity
import yamlext


def _GetParameterType(data):
    """
    Guesses parameter type based on loaded data
    :param data: loaded parameter data
    :return: parameter type name
    """
    if 'type' in data:
        return data['type']
    if isinstance(data['value'], (str, unicode)):
        return 'texture'
    if isinstance(data['value'], tuple):
        if len(data['value']) == 2:
            return 'vector2'
        elif len(data['value']) == 3:
            return 'vector3'
        elif len(data['value']) == 4:
            return 'vector4'
        else:
            raise ValueError()
    if isinstance(data['value'], bool):
        return 'bool'
    if isinstance(data['value'], (float, int, long)):
        return 'float'
    raise ValueError()


def _GetConditionDependencies(condition):
    """
    Returns dependency names from a condition string
    :param condition: string containing a condition expression
    :return: list of names in the condition expression
    """
    dependencies = []
    for node in ast.walk(ast.parse(condition)):
        if isinstance(node, ast.Name):
            dependencies.append(node.id)
    return dependencies


def _FindNamedItem(items, name):
    for each in items:
        if each.name == name:
            return each
    raise KeyError()


class _LazyParameters(object):
    """
    Interface for "eval" parameter to provide variable values in a lazy fation
    """
    def __init__(self, parameters):
        self._parameters = parameters

    def __getitem__(self, item):
        return self._parameters[item].GetValue()


def _EvaluateCondition(condition, parameters):
    """
    Evaluates a condition expression
    :param condition: condition expression string
    :param parameters: dict of parameters (Parameter objects)
    :return: result of evaluating expression
    """
    return eval(condition, {'platform': trinity.platform}, _LazyParameters(parameters))


class Parameter(object):
    """
    Base class for post-process parameters
    """
    def __init__(self, name, data):
        self.name = name
        "parameter name"
        self.group = data.get('group')
        "parameter group for Jessica"
        self.description = data.get('description', '')
        "parameter description"
        self._type = _GetParameterType(data)
        self._bindings = {}

    def UpdateValue(self, parameters):
        """
        Updates the internal parameter value and all its bindings
        :param parameters: all post-process parameter objects
        """
        self._UpdateBindings()

    def GetValue(self):
        pass

    def GetExposedValue(self):
        return self.GetValue()

    def SetValue(self, value):
        pass

    def SetExposedValue(self, value):
        self.SetValue(value)

    def _GetEffectParameter(self, effect, name):
        raise NotImplementedError()

    def _ApplyToObject(self, obj, name):
        setattr(obj, name, self.GetValue())

    def _ApplyToEffect(self, obj, name):
        self._ApplyToObject(obj, name)

    def Bind(self, obj, name):
        if isinstance(obj, trinity.Tr2Effect):
            self._bindings[(obj, name)] = self._GetEffectParameter(obj, name) + (self._ApplyToEffect,)
        else:
            self._bindings[(obj, name)] = (obj, name, self._ApplyToObject)

    def Unbind(self, obj, name):
        try:
            del self._bindings[(obj, name)]
        except KeyError:
            pass

    def GetDependencies(self):
        return ()

    def _UpdateBindings(self):
        for obj, name, apply in self._bindings.itervalues():
            apply(obj, name)

    def UpdateUsage(self, usage):
        usage[self.name] = True

    def Load(self, parameters):
        pass

    def Unload(self):
        pass


class NumericParameter(Parameter):
    """
    Numeric (float or vector) parameter type.
    """
    def __init__(self, name, data):
        super(NumericParameter, self).__init__(name, data)
        self.value = data['value']
        if self._type == 'float':
            self.paramType = trinity.Tr2FloatParameter
        elif self._type == 'vector2':
            self.paramType = trinity.Tr2Vector2Parameter
        elif self._type == 'vector3':
            self.paramType = trinity.Tr2Vector3Parameter
        elif self._type == 'vector4':
            self.paramType = trinity.Tr2Vector4Parameter
        else:
            raise RuntimeError()

    def _GetEffectParameter(self, effect, name):
        try:
            param = _FindNamedItem(effect.parameters, name)
        except KeyError:
            param = self.paramType()
            param.name = name
            effect.parameters.append(param)
        return param, 'value'

    def _ApplyToEffect(self, obj, name):
        obj.value = self.value

    def GetValue(self):
        return self.value

    def SetValue(self, value):
        self.value = value


class BooleanParameter(Parameter):
    """
    Boolean parameter type. Mapping it effect parameters, produces Tr2FloatParameter
    """
    def __init__(self, name, data):
        super(BooleanParameter, self).__init__(name, data)
        self.value = data['value']
        self.paramType = trinity.Tr2FloatParameter

    def GetValue(self):
        return self.value

    def SetValue(self, value):
        self.value = value

    def _GetEffectParameter(self, effect, name):
        try:
            param = _FindNamedItem(effect.parameters, name)
        except KeyError:
            param = trinity.Tr2FloatParameter()
            param.name = name
            effect.parameters.append(param)
        return param, 'value'

    def _ApplyToEffect(self, obj, name):
        obj.value = 1 if self.value else 0


class TextureParameter(Parameter):
    """
    Texture parameter with texture loaded from a path
    """
    def __init__(self, name, data):
        super(TextureParameter, self).__init__(name, data)
        if self._type != 'texture':
            raise RuntimeError()
        self.resourcePath = data['value']
        self.resource = blue.resMan.GetResource(self.resourcePath)
        self.resource.name = name

    def GetValue(self):
        return self.resource

    def SetValue(self, value):
        self.resourcePath = value
        self.resource = blue.resMan.GetResource(self.resourcePath)
        self.resource.name = self.name

    def GetExposedValue(self):
        return self.resourcePath

    def _GetEffectParameter(self, effect, name):
        try:
            param = _FindNamedItem(effect.resources, name)
        except KeyError:
            param = trinity.TriTextureParameter()
            param.name = name
            effect.resources.append(param)
        return param, 'resourcePath'

    def _ApplyToEffect(self, obj, name):
        obj.resourcePath = self.resourcePath


class GpuBufferParameter(Parameter):
    """
    GPU buffer parameter with buffer initialized from parameter data
    """
    def __init__(self, name, data):
        super(GpuBufferParameter, self).__init__(name, data)
        if self._type != 'gpubuffer':
            raise RuntimeError()
        reader = blue.DictReader()
        self.buffer = reader.CreateObject(data['buffer'])

    def GetValue(self):
        return self.buffer

    def SetValue(self, value):
        self.buffer = value

    def _GetEffectParameter(self, effect, name):
        try:
            param = _FindNamedItem(effect.resources, name)
        except KeyError:
            param = trinity.Tr2GeometryBufferParameter()
            param.name = name
            effect.resources.append(param)
        return param, 'gpuBuffer'

    def _ApplyToEffect(self, obj, name):
        obj.gpuBuffer = self.buffer


class BuiltinRenderTargetParameter(Parameter):
    """
    Externally-provided render target parameter (source, destination render targets)
    """
    def __init__(self, name, rt):
        super(BuiltinRenderTargetParameter, self).__init__(name, {'type': 'rendertarget'})
        self.rt = rt
        self.texture = trinity.TriTextureRes()
        self.texture.name = self.name
        self.texture.SetFromRenderTarget(self.rt)

    def GetValue(self):
        return self.rt

    def SetValue(self, value):
        self.rt = value
        self.texture.SetFromRenderTarget(self.rt)

    def _GetEffectParameter(self, effect, name):
        try:
            param = _FindNamedItem(effect.resources, name)
        except KeyError:
            param = trinity.TriTextureParameter()
            param.name = name
            effect.resources.append(param)
        return param, 'resourcePath'

    def _ApplyToEffect(self, obj, name):
        obj.SetResource(self.texture)


class RenderTargetParameter(Parameter):
    """
    Render target parameter. Render targets are created and maintained by objects of this class.
    """
    def __init__(self, name, data):
        super(RenderTargetParameter, self).__init__(name, data)
        if self._type != 'rendertarget':
            raise RuntimeError()
        self._data = data
        self.rt = None
        self.texture = trinity.TriTextureRes()
        self.texture.name = self.name

    def UpdateValue(self, parameters):
        if 'copyFrom' in self._data:
            copyFrom = parameters[self._data['copyFrom']].GetValue()
            if copyFrom:
                if 'width' in self._data:
                    if isinstance(self._data['width'], float):
                        width = int(self._data['width'] * copyFrom.width)
                    else:
                        width = self._data['width']
                else:
                    width = copyFrom.width
                if 'height' in self._data:
                    if isinstance(self._data['height'], float):
                        height = int(self._data['height'] * copyFrom.height)
                    else:
                        height = self._data['height']
                else:
                    height = copyFrom.height
                self.rt = trinity.Tr2RenderTarget(width, height, self._data.get('mipCount', copyFrom.mipCount),
                                                  self._data.get('format', copyFrom.format),
                                                  self._data.get('multiSampleType', copyFrom.multiSampleType),
                                                  self._data.get('multiSampleQuality', copyFrom.multiSampleQuality))
                self.rt.name = self.name
            else:
                self.rt = None
        else:
            self.rt = trinity.Tr2RenderTarget(self._data['width'], self._data['height'], self._data.get('mipCount', 1),
                                              self._data['format'], self._data.get('multiSampleType', 1),
                                              self._data.get('multiSampleQuality', 0))
            self.rt.name = self.name
        self.texture.SetFromRenderTarget(self.rt)
        self._UpdateBindings()

    def GetValue(self):
        return self.rt

    def _GetEffectParameter(self, effect, name):
        try:
            param = _FindNamedItem(effect.resources, name)
        except KeyError:
            param = trinity.TriTextureParameter()
            param.name = name
            effect.resources.append(param)
        return param, 'resourcePath'

    def _ApplyToObject(self, obj, name):
        setattr(obj, name, self.GetValue())

    def _ApplyToEffect(self, obj, name):
        obj.SetResource(self.texture)

    def GetDependencies(self):
        if 'copyFrom' in self._data:
            return self._data['copyFrom'],
        return ()

    def UpdateUsage(self, usage):
        super(RenderTargetParameter, self).UpdateUsage(usage)
        if 'copyFrom' in self._data:
            usage[self._data['copyFrom']] = True

    def Load(self, parameters):
        if not self.rt:
            self.UpdateValue(parameters)
    def Unload(self):
        self.rt = None
        self._UpdateBindings()


class ConditionParameter(Parameter):
    """
    Conditional parameter
    """
    def __init__(self, name, data):
        super(ConditionParameter, self).__init__(name, data)
        if self._type != 'condition':
            raise RuntimeError()
        self.condition = data['condition']
        self.true = data[True]
        self.false = data[False]
        self.active = None

        self._dependencies = [self.true, self.false] + _GetConditionDependencies(data['condition'])

    def UpdateValue(self, parameters):
        if _EvaluateCondition(self.condition, parameters):
            active = parameters[self.true]
        else:
            active = parameters[self.false]
        if self.active != active:
            for obj, name in self._bindings:
                self.active.Unbind(obj, name)
            self.active = active
            for obj, name in self._bindings:
                self.active.Bind(obj, name)
        self.active.UpdateValue(parameters)

    def GetValue(self):
        return self.active.GetValue()

    def GetDependencies(self):
        return self._dependencies

    def Bind(self, obj, name):
        super(ConditionParameter, self).Bind(obj, name)
        if self.active:
            self.active.Bind(obj, name)

    def Unbind(self, obj, name):
        super(ConditionParameter, self).Unbind(obj, name)
        if self.active:
            self.active.Bind(obj, name)

    def _GetEffectParameter(self, effect, name):
        return None, None

    def UpdateUsage(self, usage):
        super(ConditionParameter, self).UpdateUsage(usage)
        if self.active:
            self.active.UpdateUsage(usage)


PARAMETER_TYPES = {'condition': ConditionParameter, 'rendertarget': RenderTargetParameter,
                   'texture': TextureParameter, 'vector2': NumericParameter,
                   'vector3': NumericParameter, 'vector4': NumericParameter,
                   'float': NumericParameter, 'bool': BooleanParameter, 'gpubuffer': GpuBufferParameter}


class PostProcess(object):
    def __init__(self):
        super(PostProcess, self).__setattr__('renderJob', trinity.TriRenderJob())
        self.renderJob.name = 'Post Process'
        self.renderJob.enabled = False
        super(PostProcess, self).__setattr__('source', None)
        super(PostProcess, self).__setattr__('dest', None)
        super(PostProcess, self).__setattr__('_data', None)
        super(PostProcess, self).__setattr__('_rj', trinity.TriRenderJob())
        super(PostProcess, self).__setattr__('_parameters', {
            '__sourcert__': BuiltinRenderTargetParameter('__sourcert__', self.source),
            '__destrt__': BuiltinRenderTargetParameter('__sourcert__', self.dest)})
        super(PostProcess, self).__setattr__('_dependencies', {})
        super(PostProcess, self).__setattr__('_stepDependencies', [])
        super(PostProcess, self).__setattr__('_builtInParameters', self._parameters.keys())
        super(PostProcess, self).__setattr__('__members__', [])
        super(PostProcess, self).__setattr__('_loadPending', False)

        self.Clear()

    def LoadParameters(self, path):
        """
        Loads a YAML file with parameter values
        :param path: path to parameter YAML file
        :jessica-param-widget path: filepath
        :jessica-favorite:
        """
        params = yamlext.load(blue.paths.GetFileContentsWithYield(path))
        for name, value in params.iteritems():
            self._parameters[name].SetValue(value)
        self._UpdateParameters()

    def SaveParameters(self, path):
        """
        Save parameter values into a YAML file
        :param path: path to parameter YAML file
        :jessica-param-widget path: filepath-save
        :jessica-favorite:
        """
        params = {}
        for name, param in self._parameters.iteritems():
            value = param.GetValue()
            if isinstance(value, (int, long, float, tuple, bool)):
                params[name] = value
        yamlext.dumpfile(params, blue.paths.ResolvePathForWriting(path))

    def Clear(self):
        """
        Clears post-process object. Restores it to a default state of copying source render target to destination.
        """
        data = """
parameters:
    _source:
        type: condition
        condition: __sourcert__ and __sourcert__.multiSampleType > 1
        true: _sourceCopy
        false: __sourcert__
    _sourceCopy:
        type: rendertarget
        multiSampleType: 1
        multiSampleQuality: 0
        copyFrom: __sourcert__
steps:
-   type: Resolve
    name: Resolve Source into Dest
    condition: __sourcert__.multiSampleType > 1 and __destrt__
    arguments:
        -   __destrt__
        -   __sourcert__
    parameters:
        destination: __destrt__
        source: __sourcert__
-   type: Resolve
    name: Resolve Source into a Temp RT
    condition: __sourcert__.multiSampleType > 1 and not __destrt__
    arguments:
        -   _sourceCopy
        -   __sourcert__
    parameters:
        destination: _sourceCopy
        source: __sourcert__

-   type: PushDepthStencil
    name: Push NULL DS
    parameters:
        pushCurrent: False
-   type: PushRenderTarget
    name: Backup RT 0
    parameters:
        renderTarget: __destrt__

-   type: RenderTexture
    name: Render to Dest
    condition: not __destrt__
    arguments:
        -   _source
    parameters:
        renderTarget: _source

-   type: PopDepthStencil
    name: Restore DS
-   type: PopRenderTarget
    name: Restore RT 0
"""
        self._data = yamlext.loads(data)
        del self.renderJob.steps[:]
        if self.source:
            self._LoadData(self._data)
            super(PostProcess, self).__setattr__('_loadPending', False)
        else:
            super(PostProcess, self).__setattr__('_loadPending', True)

    def _SetVariable(self, name, value):
        self._parameters[name].SetExposedValue(value)
        self._UpdateParameters((name,))

    def SetSource(self, source):
        """
        Assigns source render target for post-processing
        :param source: Source render target
        """
        super(PostProcess, self).__setattr__('source', source)
        self._SetVariable('__sourcert__', source)
        self.renderJob.enabled = True if source else False
        if self.source and self._loadPending:
            self._LoadData(self._data)
            super(PostProcess, self).__setattr__('_loadPending', False)

    def SetDest(self, dest):
        """
        Assigns destination render target
        :param dest: Destination render target
        :return:
        """
        super(PostProcess, self).__setattr__('dest', dest)
        self._SetVariable('__destrt__', dest)

    def _ExpandChangedParams(self, changedParams=None):
        if changedParams is None:
            changedParams = self._parameters.keys()
        cp = set(changedParams)
        for each in changedParams:
            cp = cp.union(self._dependencies.get(each, []))
        return cp

    def _UpdateParameters(self, changedParams=None):
        def dep_cmp(a, b):
            if a in self._dependencies.get(b, []):
                return 1
            if b in self._dependencies.get(a, []):
                return -1
            return 0

        changedParams = sorted(self._ExpandChangedParams(changedParams), dep_cmp)
        for p in changedParams:
            self._parameters[p].UpdateValue(self._parameters)

        used = {k: False for k in self._parameters.iterkeys()}
        for params, condition, steps in self._stepDependencies:
            if condition:
                enabled = True if _EvaluateCondition(condition, self._parameters) else False
            else:
                enabled = True
            if params.intersection(changedParams):
                for step in steps:
                    step.enabled = enabled
            if enabled:
                for name in params:
                    self._parameters[name].UpdateUsage(used)
        for name, is_used in used.iteritems():
            if is_used:
                self._parameters[name].Load(self._parameters)
            else:
                self._parameters[name].Unload()

    def Load(self, path):
        """
        Loads post-processing configuration from YAML file.
        :param path: path to YAML file
        :jessica-param-widget path: filepath
        """
        self.Clear()
        self._data = yamlext.load(blue.paths.GetFileContentsWithYield(path))
        if self.source:
            self._LoadData(self._data)
            super(PostProcess, self).__setattr__('_loadPending', False)
        else:
            super(PostProcess, self).__setattr__('_loadPending', True)

    def _FlattenDependencies(self, dependencies):
        changed = True
        while changed:
            changed = False
            for k, v in dependencies.iteritems():
                for each in v:
                    u = v.union(dependencies.get(each, set()))
                    if u != v:
                        v = u
                        changed = True
                if changed:
                    dependencies[k] = v
                    break

    def _LoadData(self, data):
        del self.__members__[:]
        self._dependencies.clear()
        del self._stepDependencies[:]

        for k in list(self._parameters.keys()):
            if k not in self._builtInParameters:
                del self._parameters[k]

        for key, value in data.get('parameters', {}).iteritems():
            pt = PARAMETER_TYPES[_GetParameterType(value)]
            self._parameters[key] = pt(key, value)
            for each in self._parameters[key].GetDependencies():
                self._dependencies.setdefault(each, set()).add(key)
            self.__members__.append(key)

        self._FlattenDependencies(self._dependencies)
        self._UpdateParameters()

        del self.renderJob.steps[:]

        for each in data.get('steps', []):
            args = []
            if 'arguments' in each:
                for value in each['arguments']:
                    if isinstance(value, basestring):
                        args.append(self._parameters[value].GetValue())
                    else:
                        args.append(value)

            usedParameters = set()
            step = getattr(trinity, 'TriStep%s' % each['type'])(*tuple(args))
            for key, value in each.iteritems():
                if key not in ('type', 'parameters', 'effectParameters', 'condition', 'renderTargets', 'arguments'):
                    if isinstance(value, dict):
                        reader = blue.DictReader()
                        value = reader.CreateObject(value)
                    setattr(step, key, value)
            if 'parameters' in each:
                for key, value in each['parameters'].iteritems():
                    if isinstance(value, basestring):
                        self._parameters[value].Bind(step, key)
                        usedParameters.add(value)
                    else:
                        setattr(step, key, value)
            if 'effectParameters' in each:
                for key, value in each['effectParameters'].iteritems():
                    self._parameters[value].Bind(step.effect, key)
                    usedParameters.add(value)

            steps = [step]
            if 'condition' in each:
                if not _EvaluateCondition(each['condition'], self._parameters):
                    step.enabled = False
            for indx, rt in each.get('renderTargets', {}).iteritems():
                setrt = trinity.TriStepSetRenderTarget(self._parameters[rt].GetValue())
                self._parameters[rt].Bind(setrt, 'renderTarget')
                setrt.name = 'Set RT %s for %s' % (indx, each.get('name', ''))
                setrt.enabled = step.enabled
                self.renderJob.steps.append(setrt)
                steps.append(setrt)
            self.renderJob.steps.append(step)
            if 'condition' in each:
                self._stepDependencies.append((usedParameters.union(_GetConditionDependencies(each['condition'])), each['condition'], steps))
            else:
                self._stepDependencies.append((usedParameters, None, steps))

        self._UpdateParameters()

    def __getattr__(self, item):
        if item in self._parameters:
            return self._parameters[item].GetExposedValue()
        raise AttributeError()

    def __setattr__(self, key, value):
        if key == 'source':
            self.SetSource(value)
        elif key == 'dest':
            self.SetDest(value)
        elif key == '_data':
            super(PostProcess, self).__setattr__('_data', value)
        elif key in self._parameters:
            self._SetVariable(key, value)
        else:
            raise AttributeError()

    def _JessicaGetGroup(self, attribute):
        """
        Internal Jessica helper to get object's attribute group for the attribute panel
        :param attribute: Attribute name
        :return: Attribute's group or None
        """
        if attribute in self._parameters:
            return self._parameters[attribute].group

    def _JessicaGetDescription(self, attribute):
        """
        Internal Jessica helper to get object's attribute description (docstring)
        :param attribute: Attribute name
        :return: Attribute's description or None
        """
        if attribute in self._parameters:
            return self._parameters[attribute].description
