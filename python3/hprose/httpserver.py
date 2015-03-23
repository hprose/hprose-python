############################################################
#                                                          #
#                          hprose                          #
#                                                          #
# Official WebSite: http://www.hprose.com/                 #
#                   http://www.hprose.org/                 #
#                                                          #
############################################################

############################################################
#                                                          #
# hprose/httpserver.py                                     #
#                                                          #
# hprose httpserver for python 3.0+                        #
#                                                          #
# LastModified: Mar 8, 2015                                #
# Author: Ma Bingyao <andot@hprose.com>                    #
#                                                          #
############################################################

import re, datetime
import urllib.parse
from math import trunc
from random import random
from hprose.server import HproseService

class HproseHttpService(HproseService):
    def __init__(self, sessionName = None):
        super(HproseHttpService, self).__init__()
        self.crossDomain = False
        self.p3p = False
        self.get = True
        self.onSendHeader = None
        self._origins = {}
        self._crossDomainXmlFile = None
        self._crossDomainXmlContent = None
        self._clientAccessPolicyXmlFile = None
        self._clientAccessPolicyXmlContent = None
        self._lastModified = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
        self._etag = '"%x:%x"' % (trunc(random() * 2147483647), trunc(random() * 2147483647))

    def __call__(self, environ, start_response = None):
        result = self.handle(environ)
        # WSGI 2
        if start_response == None:
            return result
        # WSGI 1
        start_response(result[0], result[1])
        return result[2]

    def addAccessControlAllowOrigin(self, origin):
        self._origins[origin] = True

    def removeAccessControlAllowOrigin(self, origin):
        del self._origins[origin]

    def _crossDomainXmlHandler(self, environ):
        path = (environ['SCRIPT_NAME'] + environ['PATH_INFO']).lower()
        if (path == '/crossdomain.xml'):
            if ((environ.get('HTTP_IF_MODIFIED_SINCE', '') == self._lastModified) and
                (environ.get('HTTP_IF_NONE_MATCH', '') == self._etag)):
                return ['304 Not Modified', [], [b'']]
            else:
                header = [('Content-Type', 'text/xml'),
                          ('Last-Modified', self._lastModified),
                          ('Etag', self._etag)]
                return ['200 OK', header, [self._crossDomainXmlContent]]
        return False

    def _clientAccessPolicyXmlHandler(self, environ):
        path = (environ['SCRIPT_NAME'] + environ['PATH_INFO']).lower()
        if (path == '/clientaccesspolicy.xml'):
            if ((environ.get('HTTP_IF_MODIFIED_SINCE', '') == self._lastModified) and
                (environ.get('HTTP_IF_NONE_MATCH', '') == self._etag)):
                return ['304 Not Modified', [], [b'']]
            else:
                header = [('Content-Type', 'text/xml'),
                          ('Last-Modified', self._lastModified),
                          ('Etag', self._etag)]
                return ['200 OK', header, [self._clientAccessPolicyXmlContent]]
        return False

    def _header(self, environ):
        header = [('Content-Type', 'text/plain')]
        if self.p3p:
            header.append(('P3P', 'CP="CAO DSP COR CUR ADM DEV TAI PSA PSD ' +
                         'IVAi IVDi CONi TELo OTPi OUR DELi SAMi OTRi UNRi ' +
                         'PUBi IND PHY ONL UNI PUR FIN COM NAV INT DEM CNT ' +
                         'STA POL HEA PRE GOV"'))
        if self.crossDomain:
            origin = environ.get("HTTP_ORIGIN", "null")
            if origin != "null":
                if (len(self._origins) == 0) or self._origins[origin]:
                    header.append(("Access-Control-Allow-Origin", origin))
                    header.append(("Access-Control-Allow-Credentials", "true"))
            else:
                header.append(("Access-Control-Allow-Origin", "*"))
        if self.onSendHeader != None:
            self.onSendHeader(environ, header)
        return header

    def handle(self, environ):
        if (self._clientAccessPolicyXmlContent != None):
            result = self._clientAccessPolicyXmlHandler(environ)
            if (result): return result
        if (self._crossDomainXmlContent != None):
            result = self._crossDomainXmlHandler(environ)
            if (result): return result
        header = self._header(environ)
        statuscode = '200 OK'
        body = b''
        try:
            if environ['REQUEST_METHOD'] == 'GET' and self.get:
                body = self._doFunctionList(environ)
            elif environ['REQUEST_METHOD'] == 'POST':
                data = environ['wsgi.input'].read(int(environ.get("CONTENT_LENGTH", 0)))
                body = self._handle(data, environ)
        finally:
            return [statuscode, header, [body]]

    def _getCrossDomainXmlFile(self):
        return self._crossDomainXmlFile

    def _setCrossDomainXmlFile(self, value):
        self._crossDomainXmlFile = value
        f = open(value)
        try:
            self._crossDomainXmlContent = f.read()
        finally:
            f.close()

    crossDomainXmlFile = property(fget = _getCrossDomainXmlFile, fset = _setCrossDomainXmlFile)

    def _getCrossDomainXmlContent(self):
        return self._crossDomainXmlContent

    def _setCrossDomainXmlContent(self, value):
        self._crossDomainXmlFile = None
        self._crossDomainXmlContent = value

    crossDomainXmlContent = property(fget = _getCrossDomainXmlContent, fset = _setCrossDomainXmlContent)

    def _getClientAccessPolicyXmlFile(self):
        return self._clientAccessPolicyXmlFile

    def _setClientAccessPolicyXmlFile(self, value):
        self._clientAccessPolicyXmlFile = value
        f = open(value)
        try:
            self._clientAccessPolicyXmlContent = f.read()
        finally:
            f.close()

    clientAccessPolicyXmlFile = property(fget = _getClientAccessPolicyXmlFile, fset = _setClientAccessPolicyXmlFile)

    def _getClientAccessPolicyXmlContent(self):
        return self._clientAccessPolicyXmlContent

    def _setClientAccessPolicyXmlContent(self, value):
        self._clientAccessPolicyXmlFile = None
        self._clientAccessPolicyXmlContent = value

    clientAccessPolicyXmlContent = property(fget = _getClientAccessPolicyXmlContent, fset = _setClientAccessPolicyXmlContent)

################################################################################
# UrlMapMiddleware                                                             #
################################################################################

class UrlMapMiddleware:
    def __init__(self, url_mapping):
        self.__init_url_mappings(url_mapping)

    def __init_url_mappings(self, url_mapping):
        self.__url_mapping = []
        for regexp, app in url_mapping:
            if not regexp.startswith('^'):
                regexp = '^' + regexp
            if not regexp.endswith('$'):
                regexp += '$'
            compiled = re.compile(regexp)
            self.__url_mapping.append((compiled, app))

    def __call__(self, environ, start_response = None):
        script_name = environ['SCRIPT_NAME']
        path_info = environ['PATH_INFO']
        path = urllib.parse.quote(script_name) + urllib.parse.quote(path_info)
        for regexp, app in self.__url_mapping:
            if regexp.match(path): return app(environ, start_response)
        if start_response:
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b'404 Not Found']
        return ('404 Not Found', [('Content-Type', 'text/plain')], [b'404 Not Found'])

################################################################################
# HproseHttpServer                                                             #
################################################################################

class HproseHttpServer(HproseHttpService):
    def __init__(self, host = '', port = 80, app = None):
        super(HproseHttpServer, self).__init__()
        self.host = host
        self.port = port
        if app == None:
            self.app = self
        else:
            self.app = app

    def start(self):
        print("Serving on port %s:%s..." % (self.host, self.port))
        from wsgiref.simple_server import make_server
        httpd = make_server(self.host, self.port, self.app)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            exit()
