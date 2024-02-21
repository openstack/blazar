# Copyright (c) 2014 Bull.
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

from oslo_log import log as logging
from oslo_serialization import jsonutils
import webob

from blazar.db import exceptions as db_exceptions
from blazar import exceptions
from blazar.i18n import _
from blazar.manager import exceptions as manager_exceptions

LOG = logging.getLogger(__name__)


class ParsableErrorMiddleware(object):
    """Middleware which prepared body to the client

    Middleware to replace the plain text message body of an error
    response with one formatted so the client can parse it.
    Based on pecan.middleware.errordocument
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        # Request for this state, modified by replace_start_response()
        # and used when an error is being reported.
        state = {}
        faultstring = None

        def replacement_start_response(status, headers, exc_info=None):
            """Overrides the default response to make errors parsable."""
            try:
                status_code = int(status.split(' ')[0])
            except (ValueError, TypeError):  # pragma: nocover
                raise exceptions.BlazarException(_(
                    'Status {0} was unexpected').format(status))
            else:
                if status_code >= 400:
                    # Remove some headers so we can replace them later
                    # when we have the full error message and can
                    # compute the length.
                    headers = [(h, v)
                               for (h, v) in headers
                               if h.lower() != 'content-length'
                               ]
                    # Save the headers as we need to modify them.
                    state['status_code'] = status_code
                    state['headers'] = headers
                    state['exc_info'] = exc_info
                return start_response(status, headers, exc_info)

        # NOTE(sbauza): As agreed, XML is not supported with API v2, but can
        #               still work if no errors are raised
        try:
            app_iter = self.app(environ, replacement_start_response)
        except exceptions.BlazarException as e:
            faultstring = "{0} {1}".format(e.__class__.__name__, str(e))
            replacement_start_response(
                webob.response.Response(status=str(e.code)).status,
                [('Content-Type', 'application/json; charset=UTF-8')]
            )
        else:
            if not state:
                return app_iter
            try:
                res_dct = jsonutils.loads(app_iter[0])
            except ValueError:
                return app_iter
            else:
                try:
                    faultstring = res_dct['faultstring']
                except KeyError:
                    return app_iter

        traceback_marker = 'Traceback (most recent call last):'
        remote_marker = 'Remote error: '

        if not faultstring:
            return app_iter

        if traceback_marker in faultstring:
            # Cut-off traceback.
            faultstring = faultstring.split(traceback_marker, 1)[0]
            faultstring = faultstring.split('[u\'', 1)[0]
        if remote_marker in faultstring:
            # RPC calls put that string on
            try:
                faultstring = faultstring.split(
                    remote_marker, 1)[1]
            except IndexError:
                pass
        faultstring = faultstring.rstrip()

        try:
            (exc_name, exc_value) = faultstring.split(' ', 1)
        except (ValueError, AttributeError):
            LOG.warning('Incorrect Remote error %s', faultstring)
        else:
            cls = getattr(manager_exceptions, exc_name,
                          getattr(exceptions, exc_name, None))
            if cls is not None:
                faultstring = str(cls(exc_value))
                state['status_code'] = cls.code
            else:
                # Get the exception from db exceptions and hide
                # the message because could contain table/column
                # information
                cls = getattr(db_exceptions, exc_name, None)
                if cls is not None:
                    faultstring = '{0}: A database error occurred'.format(
                        cls.__name__)
                    state['status_code'] = cls.code

        # NOTE(sbauza): Client expects a JSON encoded dict
        body = [jsonutils.dump_as_bytes(
                {'error_code': state['status_code'],
                 'error_message': faultstring,
                 'error_name': state['status_code']}
                )]
        start_response(
            webob.response.Response(status=state['status_code']).status,
            state['headers'],
            state['exc_info']
        )
        return body
