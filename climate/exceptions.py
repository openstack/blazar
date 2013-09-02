# Copyright (c) 2013 Mirantis Inc.
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


class ClimateException(Exception):
    """Base Exception for the Climate.

    To correctly use this class, inherit from it and define
    a 'message' and 'code' properties.
    """
    template = "An unknown exception occurred"
    code = "UNKNOWN_EXCEPTION"

    def __init__(self, *args, **kwargs):
        super(ClimateException, self).__init__(*args)
        template = kwargs.pop('template', None)
        if template:
            self.template = template

    def __str__(self):
        return self.template % self.args

    def __repr__(self):
        if self.template != type(self).template:
            tmpl = ", template=%r" % (self.template,)
        else:
            tmpl = ""
        args = ", ".join(map(repr, self.args))
        return "%s(%s%s)" % (type(self).__name__, args, tmpl)


class NotFound(ClimateException):
    """Object not found exception."""
    template = "Object not found"
    code = "NOT_FOUND"

    def __init__(self, *args, **kwargs):
        super(NotFound, self).__init__(*args, **kwargs)
