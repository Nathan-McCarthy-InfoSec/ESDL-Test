#  This work is based on original code developed and copyrighted by TNO 2020.
#  Subsequent contributions are licensed to you by the developers of such code and are
#  made available to the Project under one or several contributor license agreements.
#
#  This work is licensed to you under the Apache License, Version 2.0.
#  You may obtain a copy of the license at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Contributors:
#      TNO         - Initial implementation
#  Manager:
#      TNO

from pyecore.ecore import EAttribute, ECollection, EEnum, EReference, EClass, EObject, EStructuralFeature
from pyecore.resources import Resource
from esdl.processing.EcoreDocumentation import EcoreDocumentation
import esdl


"""
ESDL Ecore library
Contains functions that leverage the ecore functionality to e.g. list attributes, references, attribute types, etc.

"""


def get_asset_attributes(asset, esdl_doc: EcoreDocumentation = None):
    attributes = list()
    for x in asset.eClass.eAllStructuralFeatures():
        # print('{} is of type {}'.format(x.name, x.eClass.name))
        if isinstance(x, EAttribute):
            attr = dict()
            attr['name'] = x.name
            attr['type'] = x.eType.name
            attr['required'] = x.required or x.lowerBound > 0
            # if isinstance(x., EEnum):
            #    attr['value'] = list(es.eGet(x))
            attr['value'] = asset.eGet(x)
            if attr['value'] is not None:
                if x.many:
                    if isinstance(attr['value'], ECollection):
                        if isinstance(x.eType, EStructuralFeature):
                            attr['value'] = [x.name for x in attr['value']]
                            attr['many'] = True
                        elif isinstance(x.eType, EEnum):
                            attr['value'] = [x.name for x in attr['value']]
                            attr['many'] = True
                        else:
                            # primitive type
                            attr['value'] = list(attr['value'])
                            attr['many'] = True
                            pass
                    else:
                        attr['value'] = list(x.eType.to_string(attr['value']))
                else:
                    attr['value'] = x.eType.to_string(attr['value'])
            if isinstance(x.eType, EEnum):
                attr['type'] = 'EEnum'
                attr['enum_type'] = x.eType.name
                attr['options'] = list(lit.name for lit in x.eType.eLiterals)
                attr['default'] = x.eType.default_value.name
            else:
                attr['default'] = x.eType.default_value
                if x.eType.default_value is not None:
                    attr['default'] = x.eType.to_string(x.eType.default_value)
            if x.eType.name == 'EBoolean':
                attr['options'] = ['true', 'false']
            attr['doc'] = x.__doc__
            if x.__doc__ is None and esdl_doc is not None:
                attr['doc'] = esdl_doc.get_doc(asset.eClass.name, x.name)
            if esdl_doc is not None:
                attr['unit'] = esdl_doc.get_unit(asset.eClass.name, x.name)

            attributes.append(attr)
    # print(attributes)
    attrs_sorted = sorted(attributes, key=lambda a: a['name'])
    return attrs_sorted


"""
Simple function to create a representation of an object
Used in get_get_asset_references() to format the text of a reference
"""


def string_repr(item):
    if item is None:
        return item
    if hasattr(item, 'name') and item.name is not None:
        return item.name
    if hasattr(item, 'id') and item.id is not None:
        return item.eClass.name + ' (id=' + item.id + ')'
    return item.eClass.name


"""
Creates a dict with object references
:param repr_function defines a function to create a string representation from the object
:param esdl_doc a reference to ESDLDocumentation, to add missing documentation for references (from a dynamic meta model)
:return a dict with the object references.
"""


def get_asset_references(asset, esdl_doc=None, repr_function=string_repr):
    if repr_function is None:
        repr_function = string_repr
    references = list()
    for x in asset.eClass.eAllStructuralFeatures():
        if isinstance(x, EReference):
            ref = dict()
            ref['name'] = x.name
            ref['type'] = x.eType.eClass.name
            ref['many'] = x.many
            ref['required'] = x.required
            ref['containment'] = x.containment
            # do not handle eOpposite relations that are contained, they are handled automatically in pyEcore
            # e.g. Port.energyasset and Area.containingArea
            ref['eopposite'] = x.eOpposite and x.eOpposite.containment
            ref['types'] = find_types(x)
            value = asset.eGet(x)
            ref['value'] = describe_reference_value(value, repr_function)
            if not x.many and value is not None:
                # todo: check if this is necessary, as fragment is also in value
                ref['fragment'] = value.eURIFragment()
            ref['doc'] = x.__doc__
            if x.__doc__ is None and esdl_doc is not None:
                ref['doc'] = esdl_doc.get_doc(asset.eClass.name, x.name)
            references.append(ref)
    return references


"""
Calculates the value for a reference that is send to the frontend
Return value describes the value in a dict
"""
def describe_reference_value(value, repr_function):
    if value is None:
        return {"repr": value}
    elif isinstance(value, ECollection):
        values = list()
        for item in value:
            repr_str = repr_function(item)
            refValue = dict()
            refValue['repr'] = repr_str
            refValue['type'] = item.eClass.name
            if hasattr(item, 'id'):
                refValue['id'] = item.id
            refValue['fragment'] = item.eURIFragment()
            values.append(refValue)
        return values
    else:
        refValue = dict()
        repr_str = repr_function(value)
        refValue['repr'] = repr_str
        refValue['type'] = value.eClass.name
        if hasattr(value, 'id'):
            refValue['id'] = value.id
        refValue['fragment'] = value.eURIFragment()
        return refValue


"""
Creates a list of types that can be used in a Reference
E.g. for Geometry this is Point, Line, etc. as they inherit from the Geometry class that is defined as the reference's
type.

If the reference type itself can also be instantiated (is not abstract) it is also added to the list.
This means that e.g. 
"""


def find_types(reference: EReference):
    subtype_list = list()
    for eclassifier in esdl.eClass.eClassifiers:
        if isinstance(eclassifier, EClass):
            if reference.eType.eClass in eclassifier.eAllSuperTypes() and not eclassifier.abstract:
                subtype_list.append(eclassifier.name)
    if reference.eType.eClass.abstract is False:
        subtype_list.append(reference.eType.eClass.name)
    subtype_list.sort()
    return subtype_list


"""
Instantiates a new instance of class className and returns it
"""


def instantiate_type(className: str):
    return esdl.getEClassifier(className)()


"""
Resolves a URI fragment (e.g. '//@instance.0/@area/@asset.0/@port.0') to the associated object
and returns the object
This is used for objects that have no ID attribute
"""


def resolve_fragment(resource: Resource, fragment: str):
    return resource.resolve(fragment)


"""
Calculates a list of all possible reference values for a specific reference
Was based on allInstances() for each possible subtype in the types list, but this WeakSet is shared among all loggedin
users... so now a slow version to find it by iterating through all nodes of the XML graph.
TODO: find a more efficient way then by iterating through all the elements 
"""


def get_reachable_references(root: EObject, types: list, repr_function=string_repr):
    result = list()
    for instance in root.eAllContents():
        # search through all objects to find instances of type in types
        if instance.eClass.name in types:
            ref = {'repr': repr_function(instance)}
            if hasattr(instance, 'id'):
                ref['id'] = instance.id
            ref['fragment'] = instance.eURIFragment()
            result.append(ref)

    return result
