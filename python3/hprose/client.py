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
# hprose/client.py                                         #
#                                                          #
# hprose client for python 3.0+                            #
#                                                          #
# LastModified: Mar 8, 2015                                #
# Author: Ma Bingyao <andot@hprose.com>                    #
#                                                          #
############################################################

import threading
from io import BytesIO
from sys import modules
from hprose.io import HproseTags, HproseWriter, HproseReader
from hprose.common import HproseResultMode, HproseException

class _Method(object):
    def __init__(self, invoke, name):
        self.__invoke = invoke
        self.__name = name
    def __getattr__(self, name):
        return _Method(self.__invoke, self.__name + '_' + name)
    def __call__(self, *args, **kargs):
        callback = kargs.get('callback', None)
        onerror = kargs.get('onerror', None)
        byref = kargs.get('byref', False)
        resultMode = kargs.get('resultMode', HproseResultMode.Normal)
        simple = kargs.get('simple', None)
        return self.__invoke(self.__name, list(args), callback, onerror, byref, resultMode, simple)

class _Proxy(object):
    def __init__(self, invoke):
        self.__invoke = invoke
    def __getattr__(self, name):
        return _Method(self.__invoke, name)

class _AsyncInvoke(object):
    def __init__(self, invoke, name, args, callback, onerror, byref, resultMode, simple):
        self.__invoke = invoke
        self.__name = name
        self.__args = args
        self.__callback = callback
        self.__onerror = onerror
        self.__byref = byref
        self.__resultMode = resultMode
        self.__simple = simple
    def __call__(self):
        try:
            result = self.__invoke(self.__name, self.__args, self.__byref, self.__resultMode, self.__simple)
            argcount = self.__callback.func_code.co_argcount
            if argcount == 0:
                self.__callback()
            elif argcount == 1:
                self.__callback(result)
            else:
                self.__callback(result, self.__args)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            if self.__onerror != None:
                self.__onerror(self.__name, e)

class HproseClient(object):
    def __init__(self, uri = None):
        self.__filters = []
        self.onError = None
        self.simple = False
        self._uri = uri
        self.useService(uri)

    def __getattr__(self, name):
        return _Method(self.invoke, name)

    def invoke(self, name, args = (), callback = None, onerror = None, byref = False, resultMode = HproseResultMode.Normal, simple = None):
        if simple == None: simple = self.simple
        if callback == None:
            return self.__invoke(name, args, byref, resultMode, simple)
        else:
            if isinstance(callback, str):
                callback = getattr(modules['__main__'], callback, None)
            if not hasattr(callback, '__call__'):
                raise HproseException("callback must be callable")
            if onerror == None:
                onerror = self.onError
            if onerror != None:
                if isinstance(onerror, str):
                    onerror = getattr(modules['__main__'], onerror, None)
                if not hasattr(onerror, '__call__'):
                    raise HproseException("onerror must be callable")
            threading.Thread(target = _AsyncInvoke(self.__invoke, name, args,
                                                   callback, onerror,
                                                   byref, resultMode, simple)).start()

    def useService(self, uri = None):
        if uri != None: self.setUri(uri)
        return _Proxy(self.invoke)

    def setUri(self, uri):
        self._uri = uri

    uri = property(fset = setUri)

    def getFilter(self):
        if (len(self.__filters) == 0):
            return None
        return self.__filters[0]

    def setFilter(self, _filter):
        self.__filters = []
        if _filter != None:
            self.__filters.append(_filter)

    filter = property(fget = getFilter, fset = setFilter)

    def addFilter(self, _filter):
        self.__filters.append(_filter)

    def removeFilter(self, _filter):
        self.__filters.remove(_filter)

    def _sendAndReceive(self, data):
        raise NotImplementedError

    def __doOutput(self, name, args, byref, simple):
        stream = BytesIO()
        writer = HproseWriter(stream, simple)
        stream.write(HproseTags.TagCall)
        writer.writeString(name)
        if (len(args) > 0) or byref:
            writer.reset()
            writer.writeList(args)
            if byref: writer.writeBoolean(True)
        stream.write(HproseTags.TagEnd)
        data = stream.getvalue()
        stream.close()
        for _filter in self.__filters:
            data = _filter.outputFilter(data, self)
        return data

    def __doInput(self, data, args, resultMode):
        for _filter in reversed(self.__filters):
            data = _filter.inputFilter(data, self)
        if data == None or len(data) == 0 or data[len(data) - 1:] != HproseTags.TagEnd:
            raise HproseException("Wrong Response: \r\n%s" % str(data, 'utf-8'))
        if resultMode == HproseResultMode.RawWithEndTag:
            return data
        if resultMode == HproseResultMode.Raw:
            return data[:-1]
        stream = BytesIO(data)
        reader = HproseReader(stream)
        result = None
        try:
            error = None
            while True:
                tag = stream.read(1)
                if tag == HproseTags.TagEnd:
                    break
                elif tag == HproseTags.TagResult:
                    if resultMode == HproseResultMode.Normal:
                        reader.reset()
                        result = reader.unserialize()
                    else:
                        s = reader.readRaw()
                        result = s.getvalue()
                        s.close()
                elif tag == HproseTags.TagArgument:
                    reader.reset()
                    a = reader.readList()
                    if isinstance(args, list):
                        for i in range(len(args)):
                            args[i] = a[i]
                elif tag == HproseTags.TagError:
                    reader.reset()
                    error = reader.readString()
                else:
                    raise HproseException("Wrong Response: \r\n%s" % str(data, 'utf-8'))
            if error != None:
                raise HproseException(error)
        finally:
            stream.close()
        return result

    def __invoke(self, name, args, byref, resultMode, simple):
        data = self.__doOutput(name, args, byref, simple)
        data = self._sendAndReceive(data)
        return self.__doInput(data, args, resultMode)
