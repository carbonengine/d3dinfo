import blue
import greatergranny
import trinity
from shadercompiler import effectinfo


class EffectInput(object):
    def __init__(self):
        self.name = ''
        self.usage = -1
        self.index = 0
        self.dimension = 0
        self.isInferred = True


class GeneratorDescription(object):
    def __init__(self):
        self.generator = None


class ParticleSystemElementDescription(object):
    def __init__(self, usage=0, index=0):
        self.usage = usage
        """:type: int"""
        self.index = index
        """:type: int"""
        self.element = None
        """:type: trinity.Tr2ParticleElementDeclaration"""
        self.effectInputs = {}
        """:type: dict[trinity.Tr2Effect, EffectInput]"""
        self.generators = {}
        """:type: dict[trinity.ITr2GenericEmitter, trinity.ITr2AttributeGenerator]"""

    def GetName(self):
        if self.usage != trinity.PARTICLE_ELEMENT_TYPE.CUSTOM:
            # noinspection PyCallByClass,PyTypeChecker
            return trinity.PARTICLE_ELEMENT_TYPE.GetNameFromValue(self.usage)
        if self.element:
            return self.element.name
        else:
            for each in self.effectInputs.values():
                if each.name:
                    return each.name
        return ''


def FindEffects(system, parent):
    result = set()
    for mesh in blue.FindInterface(parent, 'Tr2InstancedMesh'):
        if mesh.instanceGeometryResource != system:
            continue
        for areaType in range(14):
            for area in mesh.GetAreas(areaType):
                if area.effect:
                    result.add(area.effect)
    return list(result)


def FindEmitters(system, parent):
    result = []
    for each in blue.FindInterface(parent, 'ITr2GenericEmitter'):
        if getattr(each, 'particleSystem', None) == system:
            result.append(each)
    for each in blue.FindInterface(parent, 'EveChildParticleSphere'):
        if getattr(each, 'particleSystem', None) == system:
            result.append(each)
    return result


def _ParseAnnotations(annotations):
    byKey = {}
    for k, v in annotations.items():
        if k.startswith('ParticleElement_'):
            elements = k.split('_')
            element = byKey.setdefault(elements[-1], EffectInput())
            element.isInferred = False
            if elements[-2] == 'Name':
                element.name = v.value
            elif elements[-2] == 'Usage':
                element.usage = v.value
            elif elements[-2] == 'Index':
                element.index = v.value
            elif elements[-2] == 'Dimension':
                element.dimension = v.value
    result = {}
    for v in byKey.values():
        result[(v.usage, v.index)] = v
    return result


_VERTEX_USAGE_TO_PARTICLE_TYPE = {3: trinity.PARTICLE_ELEMENT_TYPE.LIFETIME,
                                  0: trinity.PARTICLE_ELEMENT_TYPE.POSITION,
                                  2: trinity.PARTICLE_ELEMENT_TYPE.VELOCITY,
                                  4: trinity.PARTICLE_ELEMENT_TYPE.MASS,
                                  5: trinity.PARTICLE_ELEMENT_TYPE.CUSTOM}


def _UpdateElements(dest, src):
    defValues = EffectInput()
    keys = [x for x in dir(defValues) if not x.startswith('_')]
    for k, v in src.items():
        if k not in dest:
            dest[k] = v
        else:
            for a in keys:
                if getattr(dest[k], a) == getattr(defValues, a):
                    setattr(dest[k], a, getattr(v, a))


def _DimensionFromMask(mask):
    if mask & 0b1000:
        return 4
    if mask & 0b100:
        return 3
    if mask & 0b10:
        return 2
    return 1


def GetParticleElementAnnotations(effect, cache=None):
    """
    :param effect: effect object
    :type effect: trinity.Tr2Effect
    :rtype: dict[(int, int), EffectInput]
    """
    inputs = {}
    annotations = {}
    options = {name: value for name, value in effect.options}
    frozen = tuple(options.items())

    resPath = effect.effectFilePath.lower().replace('\\', '/')
    if cache is not None and (resPath, frozen, 'GetParticleElementAnnotations') in cache:
        return set(cache[(resPath, frozen, 'GetParticleElementAnnotations')])

    def inner(shader):
        """
        :type shader: shadercompiler.effectinfo.ShaderInfo
        :return:
        """
        for option, value in shader.options:
            if option.type != effectinfo.Permutation.STATIC:
                continue
            if option.name in options:
                if options[option.name] != value:
                    return
            else:
                if option.options[option.default_index] != value:
                    return
        for technique in shader.techniques:
            for each in technique.passes:
                if effectinfo.Stages.VERTEX_SHADER in each.stages:
                    vs = each.stages[effectinfo.Stages.VERTEX_SHADER]
                    """:type: shadercompiler.effectinfo.Stage"""
                    _UpdateElements(annotations, _ParseAnnotations(vs.annotations))
                    for x in vs.inputs:
                        if x.used_mask:
                            inputs[(x.usage, x.usage_index)] = max(inputs.get((x.usage, x.usage_index), 0), x.used_mask)

    path = blue.paths.ResolvePath(effect.effectFilePath)
    for sm in effectinfo.SHADER_MODEL_NAMES.iterkeys():
        try:
            compiled = effectinfo.paths.get_compiled_path(path, sm, effectinfo.Platform.DX11)
        except ValueError:
            continue
        try:
            effect = effectinfo.EffectInfo(compiled)
        except IOError:
            continue
        count = 1
        for each in effect.permutations:
            count *= len(each.options)
        for each in xrange(count):
            inner(effect.get_shader(each))

    used = set()
    for k in inputs:
        usage, index = k
        if index < 8:
            continue
        try:
            usage = _VERTEX_USAGE_TO_PARTICLE_TYPE[usage]
        except KeyError:
            continue
        index -= 8
        if (usage, index) not in annotations:
            ei = EffectInput()
            ei.usage = usage
            ei.index = index
            ei.dimension = _DimensionFromMask(inputs[k])
            annotations[(usage, index)] = ei
        used.add((usage, index))
    for k in annotations.keys():
        if k not in used:
            del annotations[k]
    if cache is not None:
        cache[(resPath, frozen, 'GetParticleElementAnnotations')] = annotations
    return annotations


_GRANNY_NAME_TO_PARTICLE_TYPE = {'Tangent': trinity.PARTICLE_ELEMENT_TYPE.LIFETIME,
                                 'Position': trinity.PARTICLE_ELEMENT_TYPE.POSITION,
                                 'Normal': trinity.PARTICLE_ELEMENT_TYPE.VELOCITY,
                                 'Binormal': trinity.PARTICLE_ELEMENT_TYPE.MASS,
                                 'TextureCoordinates': trinity.PARTICLE_ELEMENT_TYPE.CUSTOM}


class GeneratorProxy(object):
    def MatchesElement(self, element):
        return False

    def GetName(self):
        return ''


class GrannyGeneratorProxy(GeneratorProxy):
    def __init__(self, name):
        self.name = name
        self.usage = trinity.PARTICLE_ELEMENT_TYPE.CUSTOM
        self.index = 0
        self.valid = True

        for k, v in _GRANNY_NAME_TO_PARTICLE_TYPE.items():
            if name.startswith(k):
                self.usage = v
                if len(name) > len(k):
                    self.index = int(name[len(k):])
                break

    def MatchesElement(self, element):
        return self.usage == element.usage and self.index == element.index

    def GetName(self):
        return self.name


class ParticleSphereProxy(GeneratorProxy):
    def __init__(self, usage):
        self.usage = usage
        self.valid = True

    def MatchesElement(self, element):
        return self.usage == element.usage

    def GetName(self):
        return 'ParticleSphere'


def _RebindEmitter(emitter):
    if hasattr(emitter, 'Rebind'):
        emitter.Rebind()
    elif hasattr(emitter, 'Refresh'):
        emitter.Refresh()


def _RemoveFromList(parentList, item):
    parentList.remove(item)


def _AddToList(parentList, item):
    parentList.append(item)


class ParticleSystemElementsDescription(object):
    def __init__(self, system, parent, addToList=None, removeFromList=None):
        """
        Maintains a description of a particle system along with its inputs and outputs

        :param system: particle system to describe
        :type system: trinity.Tr2ParticleSystem
        :param parent: common parent for the particle system, all of its emitters and meshes (could be the scene)
        :type parent: blue.IRoot
        :param addToList: function to call when adding things to IList (allows overriding in Jessica for undo
        functionality)
        :type addToList: None | (list, T)->None
        :param removeFromList: function to call when removing things from IList (allows overriding in Jessica for undo
        functionality)
        :type removeFromList: None | (list, T)->None

        """
        self._system = system
        self._emitters = FindEmitters(system, parent)
        """:type: list[trinity.Tr2DynamicEmitter]"""
        self._effects = FindEffects(system, parent)
        """:type: list[trinity.Tr2Effect]"""
        self._effectInputs = {effect: GetParticleElementAnnotations(effect) for effect in self._effects}
        """:type: dict[trinity.Tr2Effect, dict[(int, int), EffectInput]]"""
        self._elements = {}
        """:type: dict[(int, int), ParticleSystemElementDescription]"""
        self._cachedGeneratorProxies = {}

        self._removeFromList = removeFromList or _RemoveFromList
        self._addToList = addToList or _AddToList

        for each in system.elements:
            d = ParticleSystemElementDescription(each.elementType, each.usageIndex)
            d.element = each
            self._elements[(d.usage, d.index)] = d

        for effect, inputs in self._effectInputs.items():
            for k, each in inputs.items():
                d = self._elements.setdefault(k, ParticleSystemElementDescription(*k))
                d.effectInputs[effect] = each

        for element in self._elements.values():
            for emitter in self._emitters:
                generator = self._FindGenerator(emitter, element)
                if generator:
                    element.generators[emitter] = generator

    def _GetEmitterGenerators(self, emitter):
        if hasattr(emitter, 'generators'):
            return emitter.generators
        if isinstance(emitter, trinity.Tr2StaticEmitter):
            if emitter in self._cachedGeneratorProxies:
                return self._cachedGeneratorProxies[emitter]
            path = blue.paths.ResolvePath(emitter.geometryResourcePath)
            try:
                granny = greatergranny.GrannyFile(path)
            except IOError:
                self._cachedGeneratorProxies[emitter] = []
                return []
            if emitter.meshIndex >= len(granny.meshes):
                self._cachedGeneratorProxies[emitter] = []
                return []
            decl = granny.meshes[0].GetVertexDeclaration()
            self._cachedGeneratorProxies[emitter] = [GrannyGeneratorProxy(x) for x in decl]
            return self._cachedGeneratorProxies[emitter]
        return []

    def _FindGenerator(self, emitter, element):
        if not element.element:
            return None
        for each in self._GetEmitterGenerators(emitter):
            if isinstance(each, trinity.Tr2SphereShapeAttributeGenerator):
                if each.controlPosition and element.usage == trinity.PARTICLE_ELEMENT_TYPE.POSITION:
                    return each
                if each.controlVelocity and element.usage == trinity.PARTICLE_ELEMENT_TYPE.VELOCITY:
                    return each
            elif isinstance(each, trinity.Tr2CapsuleShapeAttributeGenerator):
                if element.usage == trinity.PARTICLE_ELEMENT_TYPE.POSITION == 1:
                    return each
                if each.controlVelocity and element.usage == trinity.PARTICLE_ELEMENT_TYPE.VELOCITY:
                    return each
            elif isinstance(each, GeneratorProxy):
                if each.MatchesElement(element):
                    return each
            elif each.name == element.element.name:
                return each
        if isinstance(emitter, trinity.EveChildParticleSphere) and element.usage in (trinity.PARTICLE_ELEMENT_TYPE.LIFETIME, trinity.PARTICLE_ELEMENT_TYPE.POSITION, trinity.PARTICLE_ELEMENT_TYPE.VELOCITY):
            self._cachedGeneratorProxies.setdefault(emitter, {})
            if element.usage not in self._cachedGeneratorProxies[emitter]:
                self._cachedGeneratorProxies[emitter][element.usage] = ParticleSphereProxy(element.usage)
            return self._cachedGeneratorProxies[emitter][element.usage]
        return None

    def _DeleteElement(self, element):
        """
        :type element:  ParticleSystemElementDescription
        """
        if element not in self._elements.values():
            raise KeyError()
        if element.element:
            self._removeFromList(self._system.elements, element.element)
        for emitter, generator in element.generators.items():
            if not isinstance(generator, GeneratorProxy):
                self._removeFromList(emitter.generators, generator)
        del self._elements[(element.usage, element.index)]

    def DeleteElement(self, element):
        """
        Deletes an elements from the particle system

        :param element: element of the particle system
        :type element:  ParticleSystemElementDescription
        """
        self._DeleteElement(element)
        self.Link()

    def PruneElements(self):
        """
        Removes all custom elements not used by effects from the particle system

        :return: True if anything was deleted
        :rtype: bool
        """
        updated = False
        for each in self._elements.values():
            if each.usage == trinity.PARTICLE_ELEMENT_TYPE.CUSTOM and not each.effectInputs:
                self._DeleteElement(each)
                updated = True
        return updated

    def PopulateElements(self):
        """
        Adds missing elements to the particle system used by effects

        :return: True if anything was added
        :rtype: bool
        """
        updated = False
        for each in self._elements.values():
            if self._PopulateElement(each):
                updated = True
        if updated:
            self.Link()
        return updated

    def RemoveUnusedGenerators(self):
        """
        Removes generators from dynamic emitters not used by the particle system

        :return: True if anything was deleted
        :rtype: bool
        """
        updated = False
        for emitter in self._emitters:
            if isinstance(emitter, trinity.Tr2StaticEmitter):
                continue
            dirty = False
            for each in self.GetUnusedGenerators(emitter):
                self._removeFromList(emitter.generators, each)
                dirty = True
                updated = True
            if dirty:
                _RebindEmitter(emitter)
        return updated

    def PopulateElement(self, element):
        """
        Adds missing particle element declaration and generators for an owned element

        :param element: element of the particle system
        :type element:  ParticleSystemElementDescription
        :return: True if anything has changed
        :rtype: bool
        """
        if self._PopulateElement(element):
            self.Link()
            return True
        return False

    def Link(self):
        """
        Re-links particle system and all emitters

        :return: True if anything has changed
        :rtype: bool
        """
        v = self._system.isValid
        self._system.UpdateElementDeclaration()
        updated = v != self._system.isValid
        for each in self._emitters:
            if isinstance(each, trinity.Tr2StaticEmitter):
                each.Spawn()
            else:
                v = getattr(each, 'isValid', True)
                _RebindEmitter(each)
                updated = updated or v != getattr(each, 'isValid', True)
        return updated

    def _PopulateElement(self, element):
        """
        :type element: ParticleSystemElementDescription
        """
        updated = False
        if not element.element:
            element.element = trinity.Tr2ParticleElementDeclaration()
            element.element.elementType = element.usage
            element.element.usageIndex = element.index
            if element.usage == trinity.PARTICLE_ELEMENT_TYPE.CUSTOM:
                for ei in element.effectInputs.values():
                    if ei.name:
                        element.element.customName = ei.name
                        break
                if not element.element.customName:
                    i = 0
                    while True:
                        element.element.customName = 'custom%s' % i
                        if all(x.customName != element.element.customName for x in self._system.elements):
                            break
                        i += 1
            self._addToList(self._system.elements, element.element)
            updated = True
        for emitter in self._emitters:
            if isinstance(emitter, trinity.Tr2StaticEmitter):
                continue
            if emitter not in element.generators:
                generator = self._FindGenerator(emitter, element)
                if not generator:
                    generator = trinity.Tr2RandomUniformAttributeGenerator()
                    generator.elementType = element.usage
                    if element.usage == trinity.PARTICLE_ELEMENT_TYPE.CUSTOM:
                        generator.customName = element.element.customName
                    self._addToList(emitter.generators, generator)
                element.generators[emitter] = generator
                updated = True
        return updated

    def AddElement(self, usage, index):
        """
        Adds a new element to the particle system. If the element is already in the particle system, the function acts
        like `PupulateElement`

        :param usage: element usage code (trinity.PARTICLE_ELEMENT_TYPE)
        :type usage: int
        :param index: element usage index
        :type index: int
        :return: True if anything has changed
        :rtype: bool
        """
        updated = False
        if (usage, index) not in self._elements:
            if usage != trinity.PARTICLE_ELEMENT_TYPE.CUSTOM:
                element = ParticleSystemElementDescription()
                element.usage = usage
                element.index = 0
                self._elements[(usage, index)] = element
                updated = True
        updated = self.PopulateElement(self._elements[(usage, index)]) or updated
        return updated

    def GetEmitters(self):
        """
        Returns all emitters emitting into the particle system
        """
        return self._emitters

    def GetParticleSystem(self):
        """
        Returns the particle system
        :rtype: trinity.Tr2ParticleSystem
        """
        return self._system

    def GetEffects(self):
        """
        Returns all effects referencing this particle system
        :rtype: list[trinity.Tr2Effect]
        """
        return self._effects

    def GetElements(self):
        """
        Returns all element descriptions of this particle system
        :rtype: list[ParticleSystemElementDescription]
        """
        return self._elements.values()

    def GetUnusedGenerators(self, emitter):
        """
        Returns all generators of the emitter not used by the particle system

        :param emitter: emitter emitting into this particle system
        :type emitter: trinity.ITr2GenericEmitter
        :rtype: list[trinity.ITr2AttributeGenerator]
        """
        used = set()
        for i, element in enumerate(self._elements.values()):
            if emitter in element.generators:
                used.add(element.generators[emitter])
        return [x for x in self._GetEmitterGenerators(emitter) if x not in used]

    def SetElementName(self, element, name):
        """
        Changes element's custom name, updating all emitters and re-linking everything

        :param element: particle element description
        :type element:  ParticleSystemElementDescription
        :param name: new element custom name
        :type name: str
        :return: True if anything has changed
        :rtype: bool
        """
        if element.usage != trinity.PARTICLE_ELEMENT_TYPE.CUSTOM:
            return False
        if element.element:
            if element.element.customName == name:
                return False
            element.element.customName = name
            for each in element.generators.values():
                each.customName = name
            self.Link()
            return True

    def ChangeGeneratorType(self, element, generator, newType):
        """
        Changes generator type

        :param element: particle system element description
        :type element: ParticleSystemElementDescription
        :param generator: existing generator
        :type generator: trinity.ITr2AttributeGenerator
        :param newType: new generator type
        :type newType: type
        """
        if issubclass(newType, (trinity.Tr2SphereShapeAttributeGenerator, trinity.Tr2SphereShapeAttributeGenerator)):
            if element.usage not in (trinity.PARTICLE_ELEMENT_TYPE.POSITION, trinity.PARTICLE_ELEMENT_TYPE.VELOCITY):
                raise ValueError()
        for emitter in self._emitters:
            if generator in emitter.generators:
                if issubclass(newType, trinity.Tr2SphereShapeAttributeGenerator):
                    existing = emitter.generators.Find('trinity.Tr2SphereShapeAttributeGenerator')
                    newGenerator = None
                    for each in existing:
                        if element.usage == trinity.PARTICLE_ELEMENT_TYPE.POSITION:
                            if not each.controlPosition:
                                each.controlPosition = True
                                newGenerator = each
                                break
                        else:
                            if not each.controlVelocity:
                                each.controlVelocity = True
                                newGenerator = each
                                break
                    if not newGenerator:
                        newGenerator = newType()
                        newGenerator.controlPosition = element.usage == trinity.PARTICLE_ELEMENT_TYPE.POSITION
                        newGenerator.controlVelocity = element.usage == trinity.PARTICLE_ELEMENT_TYPE.VELOCITY
                elif issubclass(newType, trinity.Tr2CapsuleShapeAttributeGenerator):
                    existing = emitter.generators.Find('trinity.Tr2CapsuleShapeAttributeGenerator')

                    newGenerator = None
                    for each in existing:
                        if element.usage == trinity.PARTICLE_ELEMENT_TYPE.VELOCITY:
                            if not each.controlVelocity:
                                each.controlVelocity = True
                                newGenerator = each
                                break
                        else:
                            newGenerator = each
                            break
                    if not newGenerator:
                        if element.usage == trinity.PARTICLE_ELEMENT_TYPE.VELOCITY:
                            raise ValueError()
                        newGenerator = newType()
                        newGenerator.controlVelocity = False
                else:
                    newGenerator = newType()
                    newGenerator.elementType = element.usage
                    if element.element:
                        newGenerator.customName = element.element.customName
                if isinstance(generator, trinity.Tr2SphereShapeAttributeGenerator):
                    if element.usage == trinity.PARTICLE_ELEMENT_TYPE.POSITION:
                        generator.controlPosition = False
                    elif element.usage == trinity.PARTICLE_ELEMENT_TYPE.VELOCITY:
                        generator.controlVelocity = False
                    if not generator.controlVelocity and not generator.controlPosition:
                        self._removeFromList(emitter.generators, generator)
                elif isinstance(generator, trinity.Tr2CapsuleShapeAttributeGenerator):
                    if element.usage == trinity.PARTICLE_ELEMENT_TYPE.VELOCITY:
                        generator.controlVelocity = False
                    elif generator.controlVelocity:
                        raise ValueError()
                    else:
                        self._removeFromList(emitter.generators, generator)
                else:
                    self._removeFromList(emitter.generators, generator)
                if newGenerator not in emitter.generators:
                    self._addToList(emitter.generators, newGenerator)
                if emitter in element.generators:
                    element.generators[emitter] = newGenerator
                self.Link()
                return

