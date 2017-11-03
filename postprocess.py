import ast
import logging
import math
import re

import blue
import trinity
import yamlext


def _GetValueType(value):
    """
    Guesses parameter type based on its value
    :param value: parameter value
    :return: parameter type name
    """
    if isinstance(value, (str, unicode)):
        return 'texture'
    if isinstance(value, (tuple, list)):
        if len(value) == 2:
            return 'vector2'
        elif len(value) == 3:
            return 'vector3'
        elif len(value) == 4:
            return 'vector4'
        else:
            raise ValueError()
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, (float, int, long)):
        return 'float'
    raise ValueError()


def _GetParameterType(data):
    """
    Guesses parameter type based on loaded data
    :param data: loaded parameter data
    :return: parameter type name
    """
    if 'type' in data:
        return data['type']
    return _GetValueType(data['value'])


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

    def items(self):
        return [(k, v.GetValue()) for k, v in self._parameters.iteritems()]


def _EvaluateString(expression, parameters):
    """
    Evaluates a string using parameters as variables
    :param expression: condition expression string
    :param parameters: dict of parameters (Parameter objects)
    :return: result of evaluating expression
    """
    try:
        return eval(expression, {'platform': trinity.platform, 'math': math}, _LazyParameters(parameters))
    except BaseException as e:
        params = []
        for k, v in parameters.iteritems():
            # noinspection PyBroadException
            try:
                params.append('%s = %s' % (k, v.GetValue()))
            except:
                params.append('%s = ???' % k)
                pass
        logging.exception('Exception when evaluating expression %s with parameters %s', expression, '\n'.join(params))
        raise e


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
        self._defaultValue = None

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
        for obj, name, applyFunc in self._bindings.itervalues():
            applyFunc(obj, name)

    def UpdateUsage(self, usage):
        usage[self.name] = True

    def Load(self, parameters):
        pass

    def Unload(self):
        pass

    def GetDefaultValue(self):
        return self._defaultValue


class StepAttribute(object):
    """
    Class for generic, externally provided parameters. Trinity objects f.x.
    """
    def __init__(self, name, value):
        self.name = name
        "attribute name"
        self._value = value
        self._bindings = {}

    def UpdateValue(self, parameters):
        """
        Updates the internal parameter value and all its bindings
        :param parameters: all post-process parameter objects
        """
        self._UpdateBindings()

    def GetValue(self):
        return self._value

    def GetExposedValue(self):
        return self.GetValue()

    def SetValue(self, value):
        self._value = value

    def SetExposedValue(self, value):
        self.SetValue(value)

    def _ApplyToObject(self, obj, name):
        setattr(obj, name, self.GetValue())

    def Bind(self, obj, name):
        self._bindings[(obj, name)] = (obj, name, self._ApplyToObject)

    def Unbind(self, obj, name):
        try:
            del self._bindings[(obj, name)]
        except KeyError:
            pass

    def GetDependencies(self):
        return ()

    def _UpdateBindings(self):
        for obj, name, applyFunc in self._bindings.itervalues():
            applyFunc(obj, name)

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
        if isinstance(self.value, list):
            self.value = tuple(self.value)
        self.currentValue = self.value
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
        if isinstance(self.value, basestring):
            self._dependencies = _GetConditionDependencies(self.value)
            self._compiled = compile(self.value, 'string', 'eval')
        else:
            self._dependencies = []
            self._compiled = None
            self._defaultValue = self.value

    def _GetEffectParameter(self, effect, name):
        try:
            param = _FindNamedItem(effect.parameters, name)
        except KeyError:
            param = self.paramType()
            param.name = name
            effect.parameters.append(param)
        return param, 'value'

    def _ApplyToEffect(self, obj, name):
        obj.value = self.currentValue

    def GetValue(self):
        return self.currentValue

    def SetValue(self, value):
        self.value = value

    def UpdateValue(self, parameters):
        if self._compiled:
            self.currentValue = _EvaluateString(self._compiled, parameters)
        else:
            self.currentValue = self.value
        super(NumericParameter, self).UpdateValue(parameters)

    def GetDependencies(self):
        return self._dependencies


class BooleanParameter(Parameter):
    """
    Boolean parameter type. Mapping it effect parameters, produces Tr2FloatParameter
    """
    def __init__(self, name, data):
        super(BooleanParameter, self).__init__(name, data)
        self.value = data['value']
        self.paramType = trinity.Tr2FloatParameter
        self._defaultValue = self.value

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
        self.buffer = None
        self._data = data
        self._count = self._data['count']
        self._pixel_format = self._data['format']
        self._flags = self._data['creationFlags']
        self._dependencies = []
        if isinstance(self._count, basestring):
            self._count_compiled = compile(self._count, 'string', 'eval')
        else:
            self._count_compiled = None
        if isinstance(self._pixel_format, basestring):
            self._pixel_format_compiled = compile(self._pixel_format, 'string', 'eval')
        else:
            self._pixel_format_compiled = None
        if isinstance(self._flags, basestring):
            self._flags_compiled = compile(self._flags, 'string', 'eval')
        else:
            self._flags_compiled = None

        if isinstance(self._count, basestring):
            self._dependencies += _GetConditionDependencies(self._count)
        if isinstance(self._pixel_format, basestring):
            self._dependencies += _GetConditionDependencies(self._pixel_format)
        if isinstance(self._flags, basestring):
            self._dependencies += _GetConditionDependencies(self._flags)

    def UpdateValue(self, parameters):
        if self._count_compiled:
            count = _EvaluateString(self._count_compiled, parameters)
        else:
            count = self._count
        if self._pixel_format_compiled:
            pixel_format = _EvaluateString(self._pixel_format_compiled, parameters)
        else:
            pixel_format = self._pixel_format
        if self._flags_compiled:
            flags = _EvaluateString(self._flags_compiled, parameters)
        else:
            flags = self._flags
        if not self.buffer or not self.buffer.isValid or self.buffer.count != count or self.buffer.format != pixel_format or self.buffer.creationFlags != flags:
            try:
                self.buffer = trinity.Tr2GpuBuffer(count, pixel_format, flags)
            except trinity.ALError:
                self.buffer = trinity.Tr2GpuBuffer()
        super(GpuBufferParameter, self).UpdateValue(parameters)

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

    def GetDependencies(self):
        return self._dependencies


class BuiltinRenderTargetParameter(Parameter):
    """
    Externally-provided render target parameter (source, destination, velocity, accumulation render targets)
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
            if copyFrom and copyFrom.isValid:
                if 'width' in self._data:
                    if isinstance(self._data['width'], float):
                        width = max(int(self._data['width'] * copyFrom.width), 1)
                    else:
                        width = self._data['width']
                else:
                    width = copyFrom.width
                if 'height' in self._data:
                    if isinstance(self._data['height'], float):
                        height = max(int(self._data['height'] * copyFrom.height), 1)
                    else:
                        height = self._data['height']
                else:
                    height = copyFrom.height
                self.rt = trinity.Tr2RenderTarget(width, height, self._data.get('mipCount', copyFrom.mipCount),
                                                  self._data.get('format', copyFrom.format),
                                                  self._data.get('multiSampleType', copyFrom.multiSampleType),
                                                  self._data.get('multiSampleQuality', copyFrom.multiSampleQuality),
                                                  trinity.EX_FLAG.BIND_UNORDERED_ACCESS if self._data.get('uav', False) else 0)
                self.rt.name = self.name
            else:
                self.rt = None
        else:
            self.rt = trinity.Tr2RenderTarget(self._data['width'], self._data['height'], self._data.get('mipCount', 1),
                                              self._data['format'], self._data.get('multiSampleType', 1),
                                              self._data.get('multiSampleQuality', 1),
                                              trinity.EX_FLAG.BIND_UNORDERED_ACCESS if self._data.get('uav', False) else 0)
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
        self._compiled = compile(self.condition, 'string', 'eval')

        self._dependencies = [self.true, self.false] + _GetConditionDependencies(data['condition'])

    def UpdateValue(self, parameters):
        if _EvaluateString(self._compiled, parameters):
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


def TopoSort(dependencies):
    if not dependencies:
        raise StopIteration()
    data = dict(dependencies)
    for k, v in data.items():
        v.discard(k)
    extra_items_in_deps = reduce(set.union, data.values()) - set(data.keys())
    data.update({item: set() for item in extra_items_in_deps})
    while True:
        ordered = set(item for item, dep in data.items() if not dep)
        if not ordered:
            break
        for each in ordered:
            yield each
        data = {item: (dep - ordered) for item, dep in data.items()
                if item not in ordered}
    if data:
        raise RuntimeError("A cyclic dependency exists amongst %r" % dependencies)


def _IsIdentifier(s):
    return re.match("^[_A-Za-z][_a-zA-Z0-9]*$", s)


class PostProcess(object):
    def __init__(self):
        super(PostProcess, self).__setattr__('renderJob', trinity.TriRenderJob())
        self.renderJob.name = 'Post Process'
        self.renderJob.enabled = False
        super(PostProcess, self).__setattr__('source', None)
        super(PostProcess, self).__setattr__('dest', None)
        super(PostProcess, self).__setattr__('velocity', None)
        super(PostProcess, self).__setattr__('accumulation', None)
        super(PostProcess, self).__setattr__('psData', None)
        super(PostProcess, self).__setattr__('_data', None)
        super(PostProcess, self).__setattr__('_rj', trinity.TriRenderJob())
        super(PostProcess, self).__setattr__('_parameters', {
            '__sourcert__': BuiltinRenderTargetParameter('__sourcert__', self.source),
            '__destrt__': BuiltinRenderTargetParameter('__destrt__', self.dest),
            '__velocityrt__': BuiltinRenderTargetParameter('__velocityrt__', self.velocity),
            '__accumrt__': BuiltinRenderTargetParameter('__accumrt__', self.accumulation),
            '__framepsdata__': StepAttribute('__framepsdata__', self.psData)})
        super(PostProcess, self).__setattr__('_dependencies', {})
        super(PostProcess, self).__setattr__('_dependenciesSorted', [])
        super(PostProcess, self).__setattr__('_stepDependencies', [])
        super(PostProcess, self).__setattr__('_builtInParameters', self._parameters.keys())
        super(PostProcess, self).__setattr__('__members__', [])
        super(PostProcess, self).__setattr__('_loadPending', False)
        super(PostProcess, self).__setattr__('_defaultParameterValues', {})

        self.Clear()

    def SetParameters(self, params):
        """
        Configures the post processing parameters from the supplied dictionary.
        :param params: a dictionary of parameters from which to configure.
        """
        for name, value in params.iteritems():
            if name.startswith('_'):
                continue
            self._parameters[name].SetValue(value)
        self._UpdateParameters()

    def LoadParameters(self, path):
        """
        Loads a YAML file with parameter values
        :param path: path to parameter YAML file
        :jessica-param-widget path: filepath
        :jessica-favorite:
        """
        params = yamlext.load(blue.paths.GetFileContentsWithYield(path))
        self.SetParameters(params)

    def LoadOverriddenParameters(self, path):
        params = yamlext.load(blue.paths.GetFileContentsWithYield(path))
        # Store the rollback values for the parameters
        for name in params.keys():
            if name not in self._defaultParameterValues and name in self._parameters:
                defaultValue = self.GetParameterDefaultValue(name)
                if defaultValue is not None:
                    self._defaultParameterValues[name] = defaultValue

        self.SetParameters(params)

    def RestoreOverriddenParameters(self):
        self.SetParameters(self._defaultParameterValues)
        self._defaultParameterValues.clear()

    def GetParameterDefaultValue(self, paramName):
        """
        Returns default value for a parameter. If not default value exists, the function returns None
        :param paramName: parameter name
        :type paramName: str
        """
        return self._parameters[paramName].GetDefaultValue()

    def GetParameters(self):
        """
        Creates and returns a dictionary of post processing parameters.
        This dictionary is compatible with SetParameters.
        :return: a dictionary of post processing parameters.
        """
        params = {}
        for name, param in self._parameters.iteritems():
            if name.startswith('_'):
                continue
            value = param.GetValue()
            if isinstance(value, (int, long, float, tuple, bool)):
                params[name] = value
        return params

    def SaveParameters(self, path):
        """
        Save parameter values into a YAML file
        :param path: path to parameter YAML file
        :jessica-param-widget path: filepath-save
        :jessica-favorite:
        """
        params = self.GetParameters()
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
    parameters:
        destination: __destrt__
        source: __sourcert__
-   type: Resolve
    name: Resolve Source into a Temp RT
    condition: __sourcert__.multiSampleType > 1 and not __destrt__
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
    parameters:
        renderTarget: _source

-   type: PopDepthStencil
    name: Restore DS
-   type: PopRenderTarget
    name: Restore RT 0
"""
        # noinspection PyAttributeOutsideInit
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

    def SetFramePSData(self, psData):
        super(PostProcess, self).__setattr__('psData', psData)
        self._SetVariable('__framepsdata__', psData)

    def SetVelocity(self, velocity):
        """
        Assigns velocity render target for post-processing
        :param velocity: velocity render target
        """
        super(PostProcess, self).__setattr__('velocity', velocity)
        self._SetVariable('__velocityrt__', velocity or trinity.Tr2RenderTarget())

    def SetAccumulation(self, accumulation):
        """
        Assigns accumulation render target for post-processing
        :param accumulation: accumulation render target
        """
        super(PostProcess, self).__setattr__('accumulation', accumulation)
        self._SetVariable('__accumrt__', accumulation or trinity.Tr2RenderTarget())

    def SetSource(self, source):
        """
        Assigns source render target for post-processing
        :param source: Source render target
        """
        super(PostProcess, self).__setattr__('source', source)
        self._SetVariable('__sourcert__', source or trinity.Tr2RenderTarget())
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
        old = set(changedParams)
        while True:
            cp = set(old)
            for each in cp:
                cp = cp.union({k for k, v in self._dependencies.iteritems() if each in v})
            if cp == old:
                return cp
            old = cp

    def _UpdateParameters(self, changedParams=None):
        changedParams = self._ExpandChangedParams(changedParams)
        for p in self._dependenciesSorted:
            if p in changedParams:
                self._parameters[p].UpdateValue(self._parameters)

        used = {k: False for k in self._parameters.iterkeys()}
        toUpdateUsage = set()
        for params, condition, steps in self._stepDependencies:
            if condition:
                enabled = True if _EvaluateString(condition, self._parameters) else False
            else:
                enabled = True
            if params.intersection(changedParams):
                for step in steps:
                    step.enabled = enabled
            if enabled:
                toUpdateUsage.update(params)
        for name in toUpdateUsage:
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
        # noinspection PyAttributeOutsideInit
        self._data = yamlext.load(blue.paths.GetFileContentsWithYield(path))
        if self.source:
            self._LoadData(self._data)
            super(PostProcess, self).__setattr__('_loadPending', False)
        else:
            super(PostProcess, self).__setattr__('_loadPending', True)

    def _LoadData(self, data):
        del self.__members__[:]
        self._dependencies.clear()
        del self._stepDependencies[:]

        for k in list(self._parameters.keys()):
            if k not in self._builtInParameters:
                del self._parameters[k]

        for each in self._builtInParameters:
            self._dependencies[each] = set()

        for key, value in data.get('parameters', {}).iteritems():
            self._AddVariable(key, value)
        self.__members__.sort()

        del self._dependenciesSorted[:]
        self._dependenciesSorted.extend(TopoSort(self._dependencies))
        self._UpdateParameters()

        tempVars = self._CreateTempVariables(data)

        self._UpdateParameters()

        del self.renderJob.steps[:]

        for each in data.get('steps', []):
            usedParameters = set()
            step = getattr(trinity, 'TriStep%s' % each['type'])()
            for key, value in each.iteritems():
                if key not in ('type', 'parameters', 'effectParameters', 'condition', 'renderTargets', 'stepAttributes'):
                    if isinstance(value, dict):
                        reader = blue.DictReader()
                        value = reader.CreateObject(value)
                    setattr(step, key, value)
            if 'parameters' in each:
                for key, value in each['parameters'].iteritems():
                    if isinstance(value, basestring):
                        if value in tempVars:
                            value = tempVars[value]
                        self._parameters[value].Bind(step, key)
                        usedParameters.add(value)
                    else:
                        setattr(step, key, value)
            if 'effectParameters' in each:
                for key, value in each['effectParameters'].iteritems():
                    if value in tempVars:
                        value = tempVars[value]
                    self._parameters[value].Bind(step.effect, key)
                    usedParameters.add(value)
            for key, value in each.get('stepAttributes', {}).iteritems():
                if value in self._parameters:
                    self._parameters[value].Bind(step, key)
                    usedParameters.add(value)

            steps = [step]
            if 'condition' in each:
                if not _EvaluateString(each['condition'], self._parameters):
                    step.enabled = False
            for indx, rt in each.get('renderTargets', {}).iteritems():
                setrt = trinity.TriStepSetRenderTarget(self._parameters[rt].GetValue())
                self._parameters[rt].Bind(setrt, 'renderTarget')
                setrt.name = 'Set RT %s for %s' % (indx, each.get('name', ''))
                setrt.enabled = step.enabled
                self.renderJob.steps.append(setrt)
                steps.append(setrt)
                usedParameters.add(rt)
            self.renderJob.steps.append(step)
            if 'condition' in each:
                self._stepDependencies.append((usedParameters.union(_GetConditionDependencies(each['condition'])),
                                               compile(each['condition'], 'string', 'eval'), steps))
            else:
                self._stepDependencies.append((usedParameters, None, steps))

        del self._dependenciesSorted[:]
        self._dependenciesSorted.extend(TopoSort(self._dependencies))

        self._UpdateParameters()

    def _CreateTempVariables(self, data):
        tempVars = {}
        for each in data.get('steps', []):
            for key, value in each.get('parameters', {}).iteritems():
                if isinstance(value, basestring) and not _IsIdentifier(value) and value not in tempVars:
                    name = '_ppTemp%s' % len(tempVars)
                    val = _EvaluateString(value, self._parameters)
                    self._AddVariable(name, {'value': value, 'type': _GetValueType(val)})
                    tempVars[value] = name
            for key, value in each.get('effectParameters', {}).iteritems():
                if isinstance(value, basestring) and not _IsIdentifier(value) and value not in tempVars:
                    name = '_ppTemp%s' % len(tempVars)
                    val = _EvaluateString(value, self._parameters)
                    self._AddVariable(name, {'value': value, 'type': _GetValueType(val)})
                    tempVars[value] = name
        return tempVars

    def _AddVariable(self, name, description):
        pt = PARAMETER_TYPES[_GetParameterType(description)]
        self._parameters[name] = pt(name, description)
        self._dependencies[name] = set()
        for each in self._parameters[name].GetDependencies():
            self._dependencies[name].add(each)
        self.__members__.append(name)

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
