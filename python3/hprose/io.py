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
# hprose/io.py                                             #
#                                                          #
# hprose io for python 3.0+                                #
#                                                          #
# LastModified: Mar 8, 2015                                #
# Author: Ma Bingyao <andot@hprose.com>                    #
#                                                          #
############################################################

import datetime
from io import BytesIO
from fpconst import NaN, PosInf, NegInf, isInf, isNaN, isPosInf
from inspect import isclass
from sys import modules
from threading import RLock
from uuid import UUID
from hprose.common import HproseException

ZERO = datetime.timedelta(0)

class UTC(datetime.tzinfo):
    def utcoffset(self, dt):
        return ZERO
    def tzname(self, dt):
        return "UTC"
    def dst(self, dt):
        return ZERO
utc = UTC()

class HproseTags:
# Serialize Tags #
    TagInteger = b'i'
    TagLong = b'l'
    TagDouble = b'd'
    TagNull = b'n'
    TagEmpty = b'e'
    TagTrue = b't'
    TagFalse = b'f'
    TagNaN = b'N'
    TagInfinity = b'I'
    TagDate = b'D'
    TagTime = b'T'
    TagUTC = b'Z'
    TagBytes = b'b'
    TagUTF8Char = b'u'
    TagString = b's'
    TagGuid = b'g'
    TagList = b'a'
    TagMap = b'm'
    TagClass = b'c'
    TagObject = b'o'
    TagRef = b'r'
# Serialize Marks #
    TagPos = b'+'
    TagNeg = b'-'
    TagSemicolon = b';'
    TagOpenbrace = b'{'
    TagClosebrace = b'}'
    TagQuote = b'"'
    TagPoint = b'.'
# Protocol Tags #
    TagFunctions = b'F'
    TagCall = b'C'
    TagResult = b'R'
    TagArgument = b'A'
    TagError = b'E'
    TagEnd = b'z'

_classCache1 = {}
_classCache2 = {}
_classCacheLock = RLock()

def _get_class(name):
    name = name.split('.')
    if len(name) == 1:
        return getattr(modules['__main__'], name[0], None)
    clsname = name.pop()
    modname = '.'.join(name)
    if modname in modules:
        return getattr(modules[modname], clsname, None)
    return None

def _get_class2(name, ps, i, c):
    if i < len(ps):
        p = ps[i]
        name = name[:p] + c + name[p + 1:]
        cls = _get_class2(name, ps, i + 1, '.')
        if (i + 1 < len(ps)) and (cls == None):
            cls = _get_class2(name, ps, i + 1, '_')
        return cls
    return _get_class(name)

def _get_class_by_alias(name):
    cls = getattr(modules['__main__'], name, None)
    if not isclass(cls):
        ps = []
        p = name.find('_')
        while p > -1:
            ps.append(p)
            p = name.find('_', p + 1)
        cls = _get_class2(name, ps, 0, '.')
        if  cls == None:
            cls = _get_class2(name, ps, 0, '_')
    if cls == None:
        cls = type(name, (), {})
        cls.__module__ = '__main__'
        setattr(modules['__main__'], name, cls)
    return cls

class HproseClassManager:
    def register(_class, alias):
        _classCacheLock.acquire()
        try:
            _classCache1[_class] = alias
            _classCache2[alias] = _class
        finally:
            _classCacheLock.release()
    register = staticmethod(register)

    def getClass(alias):
        if alias in _classCache2:
            return _classCache2[alias]
        _class = _get_class_by_alias(alias)
        HproseClassManager.register(_class, alias)
        return _class
    getClass = staticmethod(getClass)

    def getClassAlias(_class):
        if _class in _classCache1:
            return _classCache1[_class]
        alias = []
        if _class.__module__ != '__main__':
            alias.extend(_class.__module__.split('.'))
        alias.append(_class.__name__)
        alias = '_'.join(alias)
        HproseClassManager.register(_class, alias)
        return alias
    getClassAlias = staticmethod(getClassAlias)

def _readuntil(stream, char):
    a = []
    while True:
        c = stream.read(1)
        if (c == char) or (c == b''): break
        a.append(c)
    return b''.join(a)

def _readint(stream, char):
    s = _readuntil(stream, char)
    if s == b'': return 0
    return int(s, 10)

class HproseRawReader(object):
    def __init__(self, stream):
        self.stream = stream
    def unexpectedTag(self, tag, expectTags = None):
        if tag == b'':
            raise HproseException('No byte found in stream')
        elif expectTags == None:
            raise HproseException(
                "Unexpected serialize tag '%s' in stream" %
                str(tag, 'utf-8'))
        else:
            raise HproseException(
                "Tag '%s' expected, but '%s' found in stream" %
                (str(expectTags, 'utf-8'), str(tag, 'utf-8')))
    def readRaw(self, ostream = None, tag = None):
        if ostream == None:
            ostream = BytesIO()
        if tag == None:
            tag = self.stream.read(1)
        ostream.write(tag)
        if ((b'0' <= tag <= b'9') or
            (tag == HproseTags.TagNull) or
            (tag == HproseTags.TagEmpty) or
            (tag == HproseTags.TagTrue) or
            (tag == HproseTags.TagFalse) or
            (tag == HproseTags.TagNaN)):
            pass
        elif tag == HproseTags.TagInfinity:
            ostream.write(self.stream.read(1))
        elif ((tag == HproseTags.TagInteger) or
            (tag == HproseTags.TagLong) or
            (tag == HproseTags.TagDouble) or
            (tag == HproseTags.TagRef)):
            self.__readNumberRaw(ostream)
        elif ((tag == HproseTags.TagDate) or
            (tag == HproseTags.TagTime)):
            self.__readDateTimeRaw(ostream)
        elif (tag == HproseTags.TagUTF8Char):
            self.__readUTF8CharRaw(ostream)
        elif (tag == HproseTags.TagBytes):
            self.__readBytesRaw(ostream)
        elif (tag == HproseTags.TagString):
            self.__readStringRaw(ostream)
        elif (tag == HproseTags.TagGuid):
            self.__readGuidRaw(ostream)
        elif ((tag == HproseTags.TagList) or
            (tag == HproseTags.TagMap) or
            (tag == HproseTags.TagObject)):
            self.__readComplexRaw(ostream)
        elif (tag == HproseTags.TagClass):
            self.__readComplexRaw(ostream)
            self.readRaw(ostream)
        elif (tag == HproseTags.TagError):
            self.readRaw(ostream)
        else:
            self.unexpectedTag(tag)
        return ostream
    def __readNumberRaw(self, ostream):
        ostream.write(_readuntil(self.stream, HproseTags.TagSemicolon))
        ostream.write(HproseTags.TagSemicolon)
    def __readDateTimeRaw(self, ostream):
        s = []
        while True:
            c = self.stream.read(1)
            s.append(c)
            if ((c == HproseTags.TagSemicolon) or
                (c == HproseTags.TagUTC)): break
        ostream.write(b''.join(s))
    def __readUTF8CharRaw(self, ostream):
        s = []
        c = self.stream.read(1)
        s.append(c)
        a = ord(c)
        if (a & 0xE0) == 0xC0:
            s.append(self.stream.read(1))
        elif (a & 0xF0) == 0xE0:
            s.append(self.stream.read(2))
        elif a > 0x7F:
            raise HproseException('Bad utf-8 encoding')
        ostream.write(b''.join(s))

    def __readBytesRaw(self, ostream):
        l = _readuntil(self.stream, HproseTags.TagQuote)
        ostream.write(l)
        ostream.write(HproseTags.TagQuote)
        if l == b'':
            l = 0
        else:
            l = int(l, 10)
        ostream.write(self.stream.read(l + 1))

    def __readStringRaw(self, ostream):
        l = _readuntil(self.stream, HproseTags.TagQuote)
        ostream.write(l)
        ostream.write(HproseTags.TagQuote)
        if l == b'':
            l = 0
        else:
            l = int(l, 10)
        s = []
        i = 0
        while i < l:
            c = self.stream.read(1)
            s.append(c)
            a = ord(c)
            if (a & 0xE0) == 0xC0:
                s.append(self.stream.read(1))
            elif (a & 0xF0) == 0xE0:
                s.append(self.stream.read(2))
            elif (a & 0xF8) == 0xF0:
                s.append(self.stream.read(3))
                i += 1
            i += 1
        s.append(self.stream.read(1))
        ostream.write(b''.join(s))
    def __readGuidRaw(self, ostream):
        ostream.write(self.stream.read(38))
    def __readComplexRaw(self, ostream):
        ostream.write(_readuntil(self.stream, HproseTags.TagOpenbrace))
        ostream.write(HproseTags.TagOpenbrace)
        tag = self.stream.read(1)
        while tag != HproseTags.TagClosebrace:
            self.readRaw(ostream, tag)
            tag = self.stream.read(1)
        ostream.write(tag)

class FakeReaderRefer:
    def set(self, val):
        pass
    def read(self, index):
        raise HproseException(
                "Unexpected serialize tag '%s' in stream" %
                str(HproseTags.TagRef, 'utf-8'))
    def reset(self):
        pass

class RealReaderRefer:
    def __init__(self):
        self.ref = []
    def set(self, val):
        self.ref.append(val)
    def read(self, index):
        return self.ref[index]
    def reset(self):
        del self.ref[:]

class HproseReader(HproseRawReader):
    def __init__(self, stream, simple = False):
        super(HproseReader, self).__init__(stream)
        self.refer = FakeReaderRefer() if simple else RealReaderRefer()
        self.classref = []
    def unserialize(self):
        tag = self.stream.read(1)
        if b'0' <= tag <= b'9':
            return int(tag, 10)
        if (tag == HproseTags.TagInteger or
            tag == HproseTags.TagLong):
            return self.__readIntegerWithoutTag()
        if tag == HproseTags.TagDouble:
            return self.__readDoubleWithoutTag()
        if tag == HproseTags.TagNull:
            return None
        if tag == HproseTags.TagEmpty:
            return ''
        if tag == HproseTags.TagTrue:
            return True
        if tag == HproseTags.TagFalse:
            return False
        if tag == HproseTags.TagNaN:
            return NaN
        if tag == HproseTags.TagInfinity:
            return self.__readInfinityWithoutTag()
        if tag == HproseTags.TagDate:
            return self.readDateWithoutTag()
        if tag == HproseTags.TagTime:
            return self.readTimeWithoutTag()
        if tag == HproseTags.TagBytes:
            return self.readBytesWithoutTag()
        if tag == HproseTags.TagUTF8Char:
            return self.__readUTF8CharWithoutTag()
        if tag == HproseTags.TagString:
            return self.readStringWithoutTag()
        if tag == HproseTags.TagGuid:
            return self.readGuidWithoutTag()
        if tag == HproseTags.TagList:
            return self.readListWithoutTag()
        if tag == HproseTags.TagMap:
            return self.readMapWithoutTag()
        if tag == HproseTags.TagClass:
            self.__readClass()
            return self.readObject()
        if tag == HproseTags.TagObject:
            return self.readObjectWithoutTag()
        if tag == HproseTags.TagRef:
            return self.__readRef()
        if tag == HproseTags.TagError:
            raise HproseException(self.readString())
        self.unexpectedTag(tag)
    def checkTag(self, expectTag):
        tag = self.stream.read(1)
        if tag != expectTag:
            self.unexpectedTag(tag, expectTag)
    def checkTags(self, expectTags):
        tag = self.stream.read(1)
        if tag not in expectTags:
            self.unexpectedTag(tag, b''.join(expectTags))
        return tag
    def __readIntegerWithoutTag(self):
        return int(_readuntil(self.stream, HproseTags.TagSemicolon), 10)
    def readInteger(self):
        tag = self.stream.read(1)
        if b'0' <= tag <= b'9':
            return int(tag, 10)
        if (tag == HproseTags.TagInteger or
            tag == HproseTags.TagLong):
            return self.__readIntegerWithoutTag()
        self.unexpectedTag(tag)
    def readLongWithoutTag(self):
        return self.__readIntegerWithoutTag()
    def readLong(self):
        return self.readInteger()
    def __readDoubleWithoutTag(self):
        return float(_readuntil(self.stream, HproseTags.TagSemicolon))
    def readDouble(self):
        tag = self.stream.read(1)
        if b'0' <= tag <= b'9':
            return float(tag)
        if (tag == HproseTags.TagInteger or
            tag == HproseTags.TagLong or
            tag == HproseTags.TagDouble):
            return self.__readDoubleWithoutTag()
        if tag == HproseTags.TagNaN:
            return NaN
        if tag == HproseTags.TagInfinity:
            return self.__readInfinityWithoutTag()
        self.unexpectedTag(tag)
    def __readInfinityWithoutTag(self):
        if self.stream.read(1) == HproseTags.TagNeg:
            return NegInf
        else:
            return PosInf
    def readBoolean(self):
        tag = self.checkTags((HproseTags.TagTrue, HproseTags.TagFalse))
        return tag == HproseTags.TagTrue
    def readDateWithoutTag(self):
        year = int(self.stream.read(4), 10)
        month = int(self.stream.read(2), 10)
        day = int(self.stream.read(2), 10)
        tag = self.stream.read(1)
        if tag == HproseTags.TagTime:
            hour = int(self.stream.read(2), 10)
            minute = int(self.stream.read(2), 10)
            second = int(self.stream.read(2), 10)
            (tag, microsecond) = self.__readMicrosecond()
            if tag == HproseTags.TagUTC:
                d = datetime.datetime(year, month, day, hour, minute, second, microsecond, utc)
            else:
                d = datetime.datetime(year, month, day, hour, minute, second, microsecond)
        elif tag == HproseTags.TagUTC:
            d = datetime.datetime(year, month, day, 0, 0, 0, 0, utc)
        else:
            d = datetime.date(year, month, day)
        self.refer.set(d)
        return d
    def readDate(self):
        tag = self.stream.read(1)
        if tag == HproseTags.TagNull: return None
        if tag == HproseTags.TagRef: return self.__readRef()
        if tag == HproseTags.TagDate: return self.readDateWithoutTag()
        self.unexpectedTag(tag)
    def readTimeWithoutTag(self):
        hour = int(self.stream.read(2), 10)
        minute = int(self.stream.read(2), 10)
        second = int(self.stream.read(2), 10)
        (tag, microsecond) = self.__readMicrosecond()
        if tag == HproseTags.TagUTC:
            t = datetime.time(hour, minute, second, microsecond, utc)
        else:
            t = datetime.time(hour, minute, second, microsecond)
        self.refer.set(t)
        return t
    def readTime(self):
        tag = self.stream.read(1)
        if tag == HproseTags.TagNull: return None
        if tag == HproseTags.TagRef: return self.__readRef()
        if tag == HproseTags.TagTime: return self.readTimeWithoutTag()
        self.unexpectedTag(tag)
    def readBytesWithoutTag(self):
        b = self.stream.read(_readint(self.stream, HproseTags.TagQuote))
        self.stream.read(1)
        self.refer.set(b)
        return b
    def readBytes(self):
        tag = self.stream.read(1)
        if tag == HproseTags.TagNull: return None
        if tag == HproseTags.TagEmpty: return b''
        if tag == HproseTags.TagRef: return self.__readRef()
        if tag == HproseTags.TagBytes: return self.readBytesWithoutTag()
        self.unexpectedTag(tag)
    def __readUTF8CharWithoutTag(self):
        s = []
        c = self.stream.read(1)
        s.append(c)
        a = ord(c)
        if (a & 0xE0) == 0xC0:
            s.append(self.stream.read(1))
        elif (a & 0xF0) == 0xE0:
            s.append(self.stream.read(2))
        elif a > 0x7F:
            raise HproseException('Bad utf-8 encoding')
        return str(b''.join(s), 'utf-8')
    def __readString(self):
        l = _readint(self.stream, HproseTags.TagQuote)
        s = []
        i = 0
        while i < l:
            c = self.stream.read(1)
            s.append(c)
            a = ord(c)
            if (a & 0xE0) == 0xC0:
                s.append(self.stream.read(1))
            elif (a & 0xF0) == 0xE0:
                s.append(self.stream.read(2))
            elif (a & 0xF8) == 0xF0:
                s.append(self.stream.read(3))
                i += 1
            i += 1
        self.stream.read(1)
        s = str(b''.join(s), 'utf-8')
        return s
    def readStringWithoutTag(self):
        s = self.__readString()
        self.refer.set(s)
        return s
    def readString(self):
        tag = self.stream.read(1)
        if tag == HproseTags.TagNull: return None
        if tag == HproseTags.TagEmpty: return ''
        if tag == HproseTags.TagUTF8Char: return self.__readUTF8CharWithoutTag()
        if tag == HproseTags.TagRef: return self.__readRef()
        if tag == HproseTags.TagString: return self.readStringWithoutTag()
        self.unexpectedTag(tag)
    def readGuidWithoutTag(self):
        u = UUID(str(self.stream.read(38), 'utf-8'))
        self.refer.set(u)
        return u
    def readGuid(self):
        tag = self.stream.read(1)
        if tag == HproseTags.TagNull: return None
        if tag == HproseTags.TagRef: return self.__readRef()
        if tag == HproseTags.TagGuid: return self.readGuidWithoutTag()
        self.unexpectedTag(tag)
    def readListWithoutTag(self):
        l = []
        self.refer.set(l)
        c = _readint(self.stream, HproseTags.TagOpenbrace)
        for _ in range(c): l.append(self.unserialize())
        self.stream.read(1)
        return l
    def readList(self):
        tag = self.stream.read(1)
        if tag == HproseTags.TagNull: return None
        if tag == HproseTags.TagRef: return self.__readRef()
        if tag == HproseTags.TagList: return self.readListWithoutTag()
        self.unexpectedTag(tag)
    def readMapWithoutTag(self):
        m = {}
        self.refer.set(m)
        c = _readint(self.stream, HproseTags.TagOpenbrace)
        for _ in range(c):
            k = self.unserialize()
            v = self.unserialize()
            m[k] = v
        self.stream.read(1)
        return m
    def readMap(self):
        tag = self.stream.read(1)
        if tag == HproseTags.TagNull: return None
        if tag == HproseTags.TagRef: return self.__readRef()
        if tag == HproseTags.TagMap: return self.readMapWithoutTag()
        self.unexpectedTag(tag)
    def readObjectWithoutTag(self):
        (cls, count, fields) = self.classref[_readint(self.stream, HproseTags.TagOpenbrace)]
        obj = cls()
        self.refer.set(obj)
        for i in range(count): setattr(obj, fields[i], self.unserialize())
        self.stream.read(1)
        return obj
    def readObject(self):
        tag = self.stream.read(1)
        if tag == HproseTags.TagNull: return None
        if tag == HproseTags.TagRef: return self.__readRef()
        if tag == HproseTags.TagObject: return self.readObjectWithoutTag()
        if tag == HproseTags.TagClass:
            self.__readClass()
            return self.readObject()
        self.unexpectedTag(tag)
    def __readClass(self):
        classname = self.__readString()
        count = _readint(self.stream, HproseTags.TagOpenbrace)
        fields = [self.readString() for _ in range(count)]
        self.stream.read(1)
        cls = HproseClassManager.getClass(classname)
        self.classref.append((cls, count, fields))
    def __readRef(self):
        return self.refer.read(_readint(self.stream, HproseTags.TagSemicolon))
    def __readMicrosecond(self):
        microsecond = 0
        tag = self.stream.read(1)
        if tag == HproseTags.TagPoint:
            microsecond = int(self.stream.read(3), 10) * 1000
            tag = self.stream.read(1)
            if b'0' <= tag <= b'9':
                microsecond = microsecond + int(tag, 10) * 100 + int(self.stream.read(2), 10)
                tag = self.stream.read(1)
                if b'0' <= tag <= b'9':
                    self.stream.read(2)
                    tag = self.stream.read(1)
        return (tag, microsecond)
    def reset(self):
        del self.classref[:]
        self.refer.reset()

dict_items = type({}.items())
dict_keys = type({}.keys())
dict_values = type({}.values())

class FakeWriterRefer:
    def set(self, val):
        pass
    def write(self, val):
        return False
    def reset(self):
        pass

class RealWriterRefer:
    def __init__(self, stream):
        self.stream = stream
        self.ref = {}
        self.refcount = 0
    def set(self, val):
        self.ref[id(val)] = self.refcount
        self.refcount += 1
    def write(self, val):
        valid = id(val)
        if (valid in self.ref):
            self.stream.write(HproseTags.TagRef)
            self.stream.write(str(self.ref[valid]).encode('utf-8'))
            self.stream.write(HproseTags.TagSemicolon)
            return True
        return False
    def reset(self):
        self.ref.clear()
        self.refcount = 0

class HproseWriter(object):
    def __init__(self, stream, simple = False):
        self.stream = stream
        self.classref = {}
        self.fieldsref = []
        self.refer = FakeWriterRefer() if simple else RealWriterRefer(stream)
    def serialize(self, v):
        if v == None: self.writeNull()
        elif isinstance(v, bool): self.writeBoolean(v)
        elif isinstance(v, int): self.writeInteger(v)
        elif isinstance(v, float): self.writeDouble(v)
        elif isinstance(v, (bytes, bytearray, memoryview)): self.writeBytesWithRef(v)
        elif isinstance(v, str):
            if v == '':
                self.writeEmpty()
            elif len(v) == 1:
                self.writeUTF8Char(v)
            else:
                self.writeStringWithRef(v)
        elif isinstance(v, UUID): self.writeGuidWithRef(v)
        elif isinstance(v, (list, tuple)): self.writeListWithRef(v)
        elif isinstance(v, (dict_items, dict_keys, dict_values)): self.writeViewWithRef(v)
        elif isinstance(v, dict): self.writeMapWithRef(v)
        elif isinstance(v, (datetime.datetime, datetime.date)): self.writeDateWithRef(v)
        elif isinstance(v, datetime.time): self.writeTimeWithRef(v)
        elif isinstance(v, object): self.writeObjectWithRef(v)
        else: raise HproseException('Not support to serialize this data')
    def writeInteger(self, i):
        if 0 <= i <= 9:
            self.stream.write(str(i).encode('utf-8'))
        elif -2147483648 <= i <= 2147483647:
            self.stream.write(HproseTags.TagInteger)
            self.stream.write(str(i).encode('utf-8'))
            self.stream.write(HproseTags.TagSemicolon)
        else:
            self.writeLong(i)
    def writeLong(self, l):
        self.stream.write(HproseTags.TagLong)
        self.stream.write(str(l).encode('utf-8'))
        self.stream.write(HproseTags.TagSemicolon)
    def writeDouble(self, d):
        if isNaN(d): self.writeNaN()
        elif isInf(d): self.writeInfinity(isPosInf(d))
        else:
            self.stream.write(HproseTags.TagDouble)
            self.stream.write(str(d).encode('utf-8'))
            self.stream.write(HproseTags.TagSemicolon)
    def writeNaN(self):
        self.stream.write(HproseTags.TagNaN)
    def writeInfinity(self, positive = True):
        self.stream.write(HproseTags.TagInfinity)
        if positive:
            self.stream.write(HproseTags.TagPos)
        else:
            self.stream.write(HproseTags.TagNeg)
    def writeNull(self):
        self.stream.write(HproseTags.TagNull)
    def writeEmpty(self):
        self.stream.write(HproseTags.TagEmpty)
    def writeBoolean(self, b):
        if b:
            self.stream.write(HproseTags.TagTrue)
        else:
            self.stream.write(HproseTags.TagFalse)
    def writeDate(self, date):
        self.refer.set(date)
        if isinstance(date, datetime.datetime):
            if (date.utcoffset() != ZERO) and (date.utcoffset() != None):
                date = date.astimezone(utc)
            if date.hour == 0 and date.minute == 0 and date.second == 0 and date.microsecond == 0:
                fmt = '%c%s' % (str(HproseTags.TagDate, 'utf-8'), '%Y%m%d')
            elif date.year == 1970 and date.month == 1 and date.day == 1:
                fmt = '%c%s' % (str(HproseTags.TagTime, 'utf-8'), '%H%M%S')
            else:
                fmt = '%c%s%c%s' % (str(HproseTags.TagDate, 'utf-8'), '%Y%m%d',
                                       str(HproseTags.TagTime, 'utf-8'), '%H%M%S')
            if date.microsecond > 0:
                fmt = '%s%c%s' % (fmt, str(HproseTags.TagPoint, 'utf-8'), '%f')
            if date.utcoffset() == ZERO:
                fmt = '%s%c' % (fmt, str(HproseTags.TagUTC, 'utf-8'))
            else:
                fmt = '%s%c' % (fmt, str(HproseTags.TagSemicolon, 'utf-8'))
        else:
            fmt = '%c%s%c' % (str(HproseTags.TagDate, 'utf-8'),
                                 '%Y%m%d',
                                 str(HproseTags.TagSemicolon, 'utf-8'))
        self.stream.write(date.strftime(fmt).encode('utf-8'))
    def writeDateWithRef(self, date):
        if not self.refer.write(date): self.writeDate(date)
    def writeTime(self, time):
        self.refer.set(time)
        fmt = '%c%s' % (str(HproseTags.TagTime, 'utf-8'), '%H%M%S')
        if time.microsecond > 0:
            fmt = '%s%c%s' % (fmt, str(HproseTags.TagPoint, 'utf-8'), '%f')
        if time.utcoffset() == ZERO:
            fmt = '%s%c' % (fmt, str(HproseTags.TagUTC, 'utf-8'))
        else:
            fmt = '%s%c' % (fmt, str(HproseTags.TagSemicolon, 'utf-8'))
        self.stream.write(time.strftime(fmt).encode('utf-8'))
    def writeTimeWithRef(self, time):
        if not self.refer.write(time): self.writeTime(time)
    def writeBytes(self, b):
        self.refer.set(b)
        length = len(b)
        self.stream.write(HproseTags.TagBytes)
        if length > 0: self.stream.write(str(length).encode('utf-8'))
        self.stream.write(HproseTags.TagQuote)
        if length > 0: self.stream.write(b)
        self.stream.write(HproseTags.TagQuote)
    def writeBytesWithRef(self, b):
        if not self.refer.write(b): self.writeBytes(b)
    def writeUTF8Char(self, u):
        self.stream.write(HproseTags.TagUTF8Char)
        self.stream.write(u.encode('utf-8'))
    def writeString(self, s):
        self.refer.set(s)
        length = len(s)
        if length == 0:
            self.stream.write(('%s%s%s' % (str(HproseTags.TagString, 'utf-8'),
                                           str(HproseTags.TagQuote, 'utf-8'),
                                           str(HproseTags.TagQuote, 'utf-8'))).encode('utf-8'))
        else:
            self.stream.write(('%s%d%s%s%s' % (str(HproseTags.TagString, 'utf-8'),
                                               length,
                                               str(HproseTags.TagQuote, 'utf-8'),
                                               s,
                                               str(HproseTags.TagQuote, 'utf-8'))).encode('utf-8'))
    def writeStringWithRef(self, s):
        if not self.refer.write(s): self.writeString(s)
    def writeGuid(self, guid):
        self.refer.set(guid)
        self.stream.write(HproseTags.TagGuid)
        self.stream.write(HproseTags.TagOpenbrace)
        self.stream.write(str(guid).encode('utf-8'))
        self.stream.write(HproseTags.TagClosebrace)
    def writeGuidWithRef(self, guid):
        if not self.refer.write(guid): self.writeGuid(guid)
    def writeList(self, l):
        self.refer.set(l)
        count = len(l)
        self.stream.write(HproseTags.TagList)
        if count > 0: self.stream.write(str(count).encode('utf-8'))
        self.stream.write(HproseTags.TagOpenbrace)
        for i in range(count): self.serialize(l[i])
        self.stream.write(HproseTags.TagClosebrace)
    def writeListWithRef(self, l):
        if not self.refer.write(l): self.writeList(l)
    def writeView(self, view):
        self.refer.set(view)
        count = len(view)
        self.stream.write(HproseTags.TagList)
        if count > 0: self.stream.write(str(count).encode('utf-8'))
        self.stream.write(HproseTags.TagOpenbrace)
        for v in view: self.serialize(v)
        self.stream.write(HproseTags.TagClosebrace)
    def writeViewWithRef(self, view):
        if not self.refer.write(view): self.writeView(view)
    def writeMap(self, m):
        self.refer.set(m)
        count = len(m)
        self.stream.write(HproseTags.TagMap)
        if count > 0: self.stream.write(str(count).encode('utf-8'))
        self.stream.write(HproseTags.TagOpenbrace)
        for key in m:
            self.serialize(key)
            self.serialize(m[key])
        self.stream.write(HproseTags.TagClosebrace)
    def writeMapWithRef(self, m):
        if not self.refer.write(m): self.writeMap(m)
    def writeObject(self, obj):
        classname = HproseClassManager.getClassAlias(obj.__class__)
        if classname in self.classref:
            index = self.classref[classname]
            fields = self.fieldsref[index]
        else:
            data = vars(obj)
            fields = tuple(data.keys())
            index = self.__writeClass(classname, fields)
        self.stream.write(HproseTags.TagObject)
        self.stream.write(str(index).encode('utf-8'))
        self.stream.write(HproseTags.TagOpenbrace)
        self.refer.set(obj)
        data = vars(obj)
        count = len(fields)
        for i in range(count):
            self.serialize(data[fields[i]])
        self.stream.write(HproseTags.TagClosebrace)
    def writeObjectWithRef(self, obj):
        if not self.refer.write(obj): self.writeObject(obj)
    def __writeClass(self, classname, fields):
        count = len(fields)
        self.stream.write(HproseTags.TagClass)
        self.stream.write(str(len(classname)).encode('utf-8'))
        self.stream.write(HproseTags.TagQuote)
        self.stream.write(classname.encode('utf-8'))
        self.stream.write(HproseTags.TagQuote)
        if count > 0: self.stream.write(str(count).encode('utf-8'))
        self.stream.write(HproseTags.TagOpenbrace)
        for i in range(count):
            field = fields[i]
            self.writeString(field)
        self.stream.write(HproseTags.TagClosebrace)
        index = len(self.fieldsref)
        self.fieldsref.append(fields)
        self.classref[classname] = index
        return index
    def reset(self):
        self.classref.clear()
        del self.fieldsref[:]
        self.refer.reset()

class HproseFormatter:
    def serialize(v, simple = False):
        stream = BytesIO()
        writer = HproseWriter(stream, simple)
        writer.serialize(v)
        return stream.getvalue()
    serialize = staticmethod(serialize)

    def unserialize(s, simple = False):
        stream = BytesIO(s)
        reader = HproseReader(stream, simple)
        return reader.unserialize()
    unserialize = staticmethod(unserialize)
