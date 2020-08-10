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

import traceback

import flask
import microversion_parse
from oslo_log import log as logging
import oslo_messaging as messaging
from oslo_serialization import jsonutils
from werkzeug import datastructures

from blazar.api import context
from blazar.api.v1 import api_version_request as api_version
from blazar.db import exceptions as db_exceptions
from blazar.enforcement import exceptions as enforcement_exceptions
from blazar import exceptions as ex
from blazar.i18n import _
from blazar.manager import exceptions as manager_exceptions
from blazar.utils.openstack import exceptions as opst_exceptions

LOG = logging.getLogger(__name__)


class Rest(flask.Blueprint):
    """REST helper class."""

    def __init__(self, *args, **kwargs):
        super(Rest, self).__init__(*args, **kwargs)
        self.before_request(set_api_version_request)
        self.after_request(add_vary_header)
        self.url_prefix = kwargs.get('url_prefix', None)
        self.routes_with_query_support = []

    def get(self, rule, status_code=200, query=False):
        return self._mroute('GET', rule, status_code, query=query)

    def post(self, rule, status_code=201):
        return self._mroute('POST', rule, status_code)

    def put(self, rule, status_code=200):
        return self._mroute('PUT', rule, status_code)

    def delete(self, rule, status_code=204):
        return self._mroute('DELETE', rule, status_code)

    def _mroute(self, methods, rule, status_code=None, **kw):
        """Route helper method."""
        if type(methods) is str:
            methods = [methods]
        return self.route(rule, methods=methods, status_code=status_code, **kw)

    def route(self, rule, **options):
        """Routes REST method and its params to the actual request."""
        status = options.pop('status_code', None)
        file_upload = options.pop('file_upload', False)
        query = options.pop('query', False)

        def decorator(func):
            endpoint = options.pop('endpoint', func.__name__)

            def handler(**kwargs):
                LOG.debug("Rest.route.decorator.handler, kwargs=%s", kwargs)
                _init_resp_type(file_upload)

                # update status code
                if status:
                    flask.request.status_code = status

                if flask.request.method in ['POST', 'PUT']:
                    kwargs['data'] = request_data()

                if flask.request.endpoint in self.routes_with_query_support:
                    params = {k: v for k, v in get_request_args().items()}
                    kwargs['query'] = params

                with context.ctx_from_headers(flask.request.headers):
                    try:
                        return func(flask.request, **kwargs)
                    except ex.BlazarException as e:
                        return bad_request(e)
                    except messaging.RemoteError as e:
                        # Get the exception from enforcement, manager and
                        # common exceptions
                        cls = getattr(enforcement_exceptions, e.exc_type,
                                      getattr(ex, e.exc_type, None))
                        cls = cls or getattr(manager_exceptions, e.exc_type,
                                             getattr(ex, e.exc_type, None))
                        cls = cls or getattr(opst_exceptions, e.exc_type,
                                             getattr(ex, e.exc_type, None))
                        if cls is not None:
                            return render_error_message(cls.code, e.value,
                                                        cls.code)
                        else:
                            # Get the exception from db exceptions and hide
                            # the message because could contain table/column
                            # information
                            cls = getattr(db_exceptions, e.exc_type, None)
                            if cls is not None:
                                return render_error_message(
                                    cls.code,
                                    '{0}: A database error occurred'.format(
                                        cls.__name__),
                                    cls.code)
                            else:
                                # We obfuscate all Exceptions
                                # but Blazar ones for
                                # security reasons
                                err = 'Internal Server Error'
                                return internal_error(500, err, e)
                    except Exception as e:
                        return internal_error(500, 'Internal Server Error', e)

            if query:
                self.routes_with_query_support.append(
                    '.'.join([self.name, endpoint]))
            self.add_url_rule(rule, endpoint, handler, **options)
            self.add_url_rule(rule + '.json', endpoint, handler, **options)

            return func

        return decorator


RT_JSON = datastructures.MIMEAccept([("application/json", 1)])


def set_api_version_request():
    requested_version = get_requested_microversion()

    try:
        api_version_request = api_version.APIVersionRequest(requested_version)
    except ex.InvalidAPIVersionString:
        flask.request.api_version_request = None
        bad_request_microversion(requested_version)

    if not api_version_request.matches(
            api_version.min_api_version(),
            api_version.max_api_version()):
        flask.request.api_version_request = None
        not_acceptable_microversion(requested_version)

    flask.request.api_version_request = api_version_request


def get_requested_microversion():
    requested_version = microversion_parse.get_version(
        flask.request.headers,
        api_version.RESERVATION_SERVICE_TYPE
    )
    if requested_version is None:
        requested_version = api_version.MIN_API_VERSION
    elif requested_version == api_version.LATEST:
        requested_version = api_version.MAX_API_VERSION

    return requested_version


def add_vary_header(response):
    if flask.request.api_version_request:
        response.headers[
            api_version.VARY_HEADER] = api_version.API_VERSION_REQUEST_HEADER
        response.headers[
            api_version.API_VERSION_REQUEST_HEADER] = "{} {}".format(
            api_version.RESERVATION_SERVICE_TYPE,
            get_requested_microversion())
    return response


def not_acceptable_microversion(requested_version):
    message = ("Version {} is not supported by the API. "
               "Minimum is {} and maximum is {}.".format(
                   requested_version,
                   api_version.MIN_API_VERSION,
                   api_version.MAX_API_VERSION))

    resp = render_error_message(
        api_version.NOT_ACCEPTABLE_STATUS_CODE,
        message,
        api_version.NOT_ACCEPTABLE_STATUS_NAME,
    )
    abort_and_log(resp.status_code, message)


def bad_request_microversion(requested_version):
    message = ("API Version String {} is of invalid format. Must be of format"
               " MajorNum.MinorNum.").format(requested_version)
    resp = render_error_message(
        api_version.BAD_REQUEST_STATUS_CODE,
        message,
        api_version.BAD_REQUEST_STATUS_NAME
    )
    abort_and_log(resp.status_code, message)


def _init_resp_type(file_upload):
    """Extracts response content type."""

    # get content type from Accept header
    resp_type = flask.request.accept_mimetypes

    # url /foo.json
    if flask.request.path.endswith('.json'):
        resp_type = RT_JSON

    flask.request.resp_type = resp_type

    # set file upload flag
    flask.request.file_upload = file_upload


def render(result=None, response_type=None, status=None, **kwargs):
    """Render response to return."""
    if not result:
        result = {}
    if type(result) is dict:
        result.update(kwargs)
    elif kwargs:
        # can't merge kwargs into the non-dict res
        abort_and_log(500,
                      _("Non-dict and non-empty kwargs passed to render."))
        return

    status_code = getattr(flask.request, 'status_code', None)
    if status:
        status_code = status
    if not status_code:
        status_code = 200

    if not response_type:
        response_type = getattr(flask.request, 'resp_type', RT_JSON)

    serializer = None
    if "application/json" in response_type:
        response_type = RT_JSON
        serializer = jsonutils
    else:
        abort_and_log(400,
                      _("Content type '%s' isn't supported") % response_type)
        return

    body = serializer.dump_as_bytes(result)

    response_type = str(response_type)

    return flask.Response(response=body, status=status_code,
                          mimetype=response_type)


def request_data():
    """Method called to process POST and PUT REST methods."""
    if hasattr(flask.request, 'parsed_data'):
        return flask.request.parsed_data

    if not flask.request.content_length > 0:
        LOG.debug("Empty body provided in request")
        return dict()

    if flask.request.file_upload:
        return flask.request.data

    deserializer = None
    content_type = flask.request.mimetype
    if not content_type or content_type in RT_JSON:
        deserializer = jsonutils
    else:
        abort_and_log(400,
                      _("Content type '%s' isn't supported") % content_type)
        return

    # parsed request data to avoid unwanted re-parsings
    parsed_data = deserializer.loads(flask.request.data)
    flask.request.parsed_data = parsed_data

    return flask.request.parsed_data


def get_request_args():
    return flask.request.args


def abort_and_log(status_code, descr, exc=None):
    """Process occurred errors."""
    LOG.error("Request aborted with status code %(code)s and "
              "message '%(msg)s'", {'code': status_code, 'msg': descr})

    if exc is not None:
        LOG.error(traceback.format_exc())

    flask.abort(status_code, description=descr)


def render_error_message(error_code, error_message, error_name):
    """Render nice error message."""
    message = {
        "error_code": error_code,
        "error_message": error_message,
        "error_name": error_name
    }

    resp = render(message)
    resp.status_code = error_code

    return resp


def internal_error(status_code, descr, exc=None):
    """Called if internal error occurred."""
    LOG.error("Request aborted with status code %(code)s "
              "and message '%(msg)s'", {'code': status_code, 'msg': descr})

    if exc is not None:
        LOG.error(traceback.format_exc())

    error_code = "INTERNAL_SERVER_ERROR"
    if status_code == 501:
        error_code = "NOT_IMPLEMENTED_ERROR"

    return render_error_message(status_code, descr, error_code)


def bad_request(error):
    """Called if Blazar exception occurred."""
    if not error.code:
        error.code = 400

    LOG.debug("Validation Error occurred: error_code=%(code)s, "
              "error_message=%(msg)s, error_name=%(name)s",
              {'code': error.code, 'msg': str(error), 'name': error.code})

    return render_error_message(error.code, str(error), error.code)


def not_found(error):
    """Called if object was not found."""
    if not error.code:
        error.code = 404

    LOG.debug("Not Found exception occurred: error_code=%(code)s, "
              "error_message=%(msg)s, error_name=%(name)s",
              {'code': error.code, 'msg': str(error), 'name': error.code})

    return render_error_message(error.code, str(error), error.code)
