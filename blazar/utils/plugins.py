# Copyright (c) 2017 NTT.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import copy
from oslo_serialization import jsonutils

from blazar.manager import exceptions as manager_ex


def convert_requirements(requirements):
    """Convert the requirements to an array of strings

    Convert the requirements to an array of strings.
    ["key op value", "key op value", ...]
    """
    # TODO(frossigneux) Support the "or" operator
    # Convert text to json
    if isinstance(requirements, str):
        # Treat empty string as an empty JSON array, to avoid raising a
        # ValueError exception while loading JSON
        #
        # TODO(priteau): Only persist valid JSON to the database
        if requirements == '':
            requirements = '[]'
        try:
            requirements = jsonutils.loads(requirements)
        except ValueError:
            raise manager_ex.MalformedRequirements(rqrms=requirements)

    # Requirement list looks like ['<', '$ram', '1024']
    if _requirements_with_three_elements(requirements):
        result = []
        if requirements[0] == '=':
            requirements[0] = '=='
        string = (requirements[1][1:] + " " + requirements[0] + " " +
                  requirements[2])
        result.append(string)
        return result
    # Remove the 'and' element at the head of the requirement list
    elif _requirements_with_and_keyword(requirements):
        return [convert_requirements(x)[0] for x in requirements[1:]]

    # Empty requirement list0
    elif isinstance(requirements, list) and not requirements:
        return requirements
    else:
        raise manager_ex.MalformedRequirements(rqrms=requirements)


def _requirements_with_three_elements(requirements):
    """Return true if requirement list looks like ['<', '$ram', '1024']."""
    return (isinstance(requirements, list) and
            len(requirements) == 3 and
            isinstance(requirements[0], str) and
            isinstance(requirements[1], str) and
            isinstance(requirements[2], str) and
            requirements[0] in ['==', '=', '!=', '>=', '<=', '>', '<'] and
            len(requirements[1]) > 1 and requirements[1][0] == '$' and
            len(requirements[2]) > 0)


def _requirements_with_and_keyword(requirements):
    return (len(requirements) > 1 and
            isinstance(requirements[0], str) and
            requirements[0] == 'and' and
            all(convert_requirements(x) for x in requirements[1:]))


def list_difference(list1, list2):
    """Return a tuple that shows the differences between lists.

       Example:
         list1 = [1, 1, 2, 3, 4, 4, 4, 5]  # old list
         list2 = [1, 2, 3, 4, 7, 8, 8]     # new list
             -> ([1, 4, 4, 5], [7, 8, 8])  # (to_remove, to_add)

    """
    def list_subtract(list_a, list_b):
        result = copy.copy(list_a)
        for value in list_b:
            if value in result:
                try:
                    result.remove(value)
                except ValueError:
                    pass
        return result

    result1 = list_subtract(list1, list2)
    result2 = list_subtract(list2, list1)
    return result1, result2
