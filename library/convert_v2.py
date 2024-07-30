import inspect
import json
import logging
import re

import basyx
from basyx.aas import model
from basyx.aas.adapter.json import AASToJsonEncoder
from basyx.aas.model import Property
from basyx.aas.model.datatypes import String

logger = logging.getLogger(__name__)


class PropertySetElement(Property):
    def __key(self):
        return self.id_short

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()

    def get_property(self):
        return Property(
            id_short=self.id_short,
            value=self.value,
            value_type=self.value_type
        )


def process_dict(element_key, element_value):
    logger.debug(f'{inspect.stack()[0][3]}: {element_key}, {element_value}')
    smece = process_level(element_value, element_key)
    return model.SubmodelElementCollection(
        id_short=element_key,
        value=smece
    )


def process_list(element_key, element_value):
    logger.debug(f'{inspect.stack()[0][3]}: {element_key}, {element_value}')
    smele = list(process_level(element_value, element_key))

    if len(smele) > 0:
        if isinstance(smele[0], model.SubmodelElementCollection):
            return model.SubmodelElementList(
                id_short=element_key,
                value=smele,
                type_value_list_element=type(smele[0])
            )
        else:
            return model.SubmodelElementList(
                id_short=element_key,
                value=smele,
                type_value_list_element=type(smele[0]),
                value_type_list_element=smele[0].value_type
            )
    else:
        return model.SubmodelElementList(
            id_short=element_key,
            value=smele,
            type_value_list_element=Property,
            value_type_list_element=String
        )


def process_property(key, value, level_key) -> PropertySetElement:
    logger.debug(f'{inspect.stack()[0][3]}: {key}, {value}')
    try:
        if isinstance(value, bool):
            value_type = basyx.aas.model.datatypes.Boolean
        elif isinstance(value, int):
            value_type = basyx.aas.model.datatypes.Integer
        elif isinstance(value, float):
            value_type = basyx.aas.model.datatypes.Float
        else:
            value_type = basyx.aas.model.datatypes.String

        id_short = get_id_short(key, level_key)

        if id_short == '':
            return None

        prop = PropertySetElement(
            id_short=id_short,
            value_type=value_type,
            value=value
        )

        return prop
    except basyx.aas.model.base.AASConstraintViolation as e:
        print(e)


def process_level_element(element_key, element_value, level_key):
    logger.debug(f'{inspect.stack()[0][3]}: {element_key}, {element_value}')
    if isinstance(element_value, dict):
        return process_dict(element_key, element_value)
    elif isinstance(element_value, list):
        return process_list(element_key, element_value)
    else:
        try:
            return process_property(element_key, element_value, level_key)
        except AttributeError as e:
            print(e)


def append_level_submodel(submodel_elements, submodel_element):
    id_short = submodel_element.id_short
    if submodel_element is None:
        return submodel_elements
    elif any(se.id_short == id_short for se in submodel_elements):
        return submodel_elements

    return submodel_elements.append(submodel_element)


def process_level(level_elements, level_key):
    submodel_elements = set()
    return_submodel_elements = []

    # Process Lists:
    if isinstance(level_elements, list):
        for index, element_value in enumerate(level_elements):
            element_key = None
            submodel_element = process_level_element(element_key, element_value, level_key)
            if submodel_element is not None:
                submodel_elements.add(submodel_element)
    # Process Properties / Dicts:
    else:
        for element_key in level_elements:
            element_value = level_elements[element_key]
            submodel_element = process_level_element(element_key, element_value, level_key)
            if submodel_element is not None:
                submodel_elements.add(submodel_element)

    # Convert PropertySetElement to Property:
    for submodel_element in submodel_elements:
        if isinstance(submodel_element, PropertySetElement):
            return_submodel_elements.append(submodel_element.get_property())
        else:
            return_submodel_elements.append(submodel_element)

    return return_submodel_elements


def convert_to_submodel(object):
    submodel = model.Submodel('id')
    submodel.id = 'https://ipa.fraunhofer.de/slm-pr-ansible-facts/test/submodel'
    submodel.submodel_element = process_level(object, "")

    # with open('result.json', 'w') as f:
    #     f.write(json.dumps(submodel, cls=basyx.aas.adapter.json.AASToJsonEncoder, indent=2))

    return json.loads(
        json.dumps(submodel, cls=AASToJsonEncoder)
    )


def get_id_short(id_short, level_key=''):
    if id_short is None:
        return id_short

    if level_key is None:
        level_key = ''

    no_special_chars = re.sub('[^a-zA-Z0-9_]', '', id_short)
    no_letter_at_start_pattern = re.compile('^[^a-zA-Z].*$')

    # if id short has no letter as first char and level_key is defined:
    if no_letter_at_start_pattern.match(no_special_chars) and len(level_key) > 0:
        # append level key to idshort
        return f'{level_key}_{no_special_chars}'
    else:
        # replace all chars not being a letter:
        return re.sub(r'^[^a-zA-Z]*', '', no_special_chars)
