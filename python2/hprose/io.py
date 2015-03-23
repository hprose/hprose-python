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
# hprose io for python 2.3+                                #
#                                                          #
# LastModified: Mar 8, 2015                                #
# Author: Ma Bingyao <andot@hprose.com>                    #
#                                                          #
############################################################

from cStringIO import StringIO
import datetime
from fpconst import NaN, PosInf, NegInf, isInf, isNaN, isPosInf
from inspect import isclass
from sys import modules
from threading import RLock
from uuid import UUID
from hprose.common import HproseException

Unicode = False

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
    TagInteger = 'i'
    TagLong = 'l'
    TagDouble = 'd'
    TagNull = 'n'
    TagEmpty = 'e'
    TagTrue = 't'
    TagFalse = 'f'
    TagNaN = 'N'
    TagInfinity = 'I'
    TagDate = 'D'
    TagTime = 'T'
    TagUTC = 'Z'
    TagBytes = 'b'
    TagUTF8Char = 'u'
    TagString = 's'
    TagGuid = 'g'
    TagList = 'a'
    TagMap = 'm'
    TagClass = 'c'
    TagObject = 'o'
    TagRef = 'r'
# Serialize Marks #
    TagPos = '+'
    TagNeg = '-'
    TagSemicolon = ';'
    TagOpenbrace = '{'
    TagClosebrace = '}'
    TagQuote = '"'
    TagPoint = '.'
# Protocol Tags #
    TagFunctions = 'F'
    TagCall = 'C'
    TagResult = 'R'
    TagArgument = 'A'
    TagError = 'E'
    TagEnd = 'z'

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
        if (c == char) or (c == ''): break
        a.append(c)
    return ''.join(a)

def _readint(stream, char):
    s = _readuntil(stream, char)
    if s == '': return 0
    return int(s, 10)

class HproseRawReader(object):
    def __init__(self, stream):
        self.stream = stream
    def unexpectedTag(self, tag, expectTags = None):
        if tag == '':
            raise HproseException, "No byte found in stream"
        elif expectTags == None:
            raise HproseException, "Unexpected serialize tag '%s' in stream" % tag
        else:
            raise HproseException, "Tag '%s' expected, but '%s' found in stream" % (expectTags, tag)
    def readRaw(self, ostream = None, tag = None):
        if ostream == None:
            ostream = StringIO()
        if tag == None:
            tag = self.stream.read(1)
        ostream.write(tag)
        if ('0' <= tag <= '9' or
            tag == HproseTags.TagNull or
            tag == HproseTags.TagEmpty or
            tag == HproseTags.TagTrue or
            tag == HproseTags.TagFalse or
            tag == HproseTags.TagNaN):
            pass
        elif tag == HproseTags.TagInfinity:
            ostream.write(self.stream.read(1))
        elif (tag == HproseTags.TagInteger or
              tag == HproseTags.TagLong or
              tag == HproseTags.TagDouble or
              tag == HproseTags.TagRef):
            self.__readNumberRaw(ostream)
        elif (tag == HproseTags.TagDate or
              tag == HproseTags.TagTime):
            self.__readDateTimeRaw(ostream)
        elif tag == HproseTags.TagUTF8Char:
            self.__readUTF8CharRaw(ostream)
        elif tag == HproseTags.TagBytes:
            self.__readBytesRaw(ostream)
        elif tag == HproseTags.TagString:
            self.__readStringRaw(ostream)
        elif tag == HproseTags.TagGuid:
            self.__readGuidRaw(ostream)
        elif (tag == HproseTags.TagList or
              tag == HproseTags.TagMap or
              tag == HproseTags.TagObject):
            self.__readComplexRaw(ostream)
        elif tag == HproseTags.TagClass:
            self.__readComplexRaw(ostream)
            self.readRaw(ostream)
        elif tag == HproseTags.TagError:
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
            if (c == HproseTags.TagSemicolon or
                c == HproseTags.TagUTC): break
        ostream.write(''.join(s))
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
            raise HproseException, 'Bad utf-8 encoding'
        ostream.write(''.join(s))
    def __readBytesRaw(self, ostream):
        l = _readuntil(self.stream, HproseTags.TagQuote)
        ostream.write(l)
        ostream.write(HproseTags.TagQuote)
        if l == '':
            l = 0
        else:
            l = int(l, 10)
        ostream.write(self.stream.read(l + 1))
    def __readStringRaw(self, ostream):
        l = _readuntil(self.stream, HproseTags.TagQuote)
        ostream.write(l)
        ostream.write(HproseTags.TagQuote)
        if l == '':
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
        ostream.write(''.join(s))
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
        raise HproseException, "Unexpected serialize tag '%s' in stream" % HproseTags.TagRef
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
        self.refer = (simple and [FakeReaderRefer()] or [RealReaderRefer()])[0]
        self.classref = []
    def unserialize(self):
        tag = self.stream.read(1)
        if '0' <= tag <= '9':
            return int(tag, 10)
        if tag == HproseTags.TagInteger:
            return self.__readIntegerWithoutTag()
        if tag == HproseTags.TagLong:
            return self.__readLongWithoutTag()
        if tag == HproseTags.TagDouble:
            return self.__readDoubleWithoutTag()
        if tag == HproseTags.TagNull:
            return None
        if tag == HproseTags.TagEmpty:
            return (Unicode and [u''] or [''])[0]
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
            raise HproseException, self.readString()
        self.unexpectedTag(tag)
    def checkTag(self, expectTag):
        tag = self.stream.read(1)
        if tag != expectTag:
            self.unexpectedTag(tag, expectTag)
    def checkTags(self, expectTags):
        tag = self.stream.read(1)
        if tag not in expectTags:
            self.unexpectedTag(tag, ''.join(expectTags))
        return tag
    def __readIntegerWithoutTag(self):
        return int(_readuntil(self.stream, HproseTags.TagSemicolon), 10)
    def readInteger(self):
        tag = self.stream.read(1)
        if '0' <= tag <= '9':
            return int(tag, 10)
        if tag == HproseTags.TagInteger:
            return self.__readIntegerWithoutTag()
        self.unexpectedTag(tag)
    def __readLongWithoutTag(self):
        return long(_readuntil(self.stream, HproseTags.TagSemicolon))
    def readLong(self):
        tag = self.stream.read(1)
        if '0' <= tag <= '9':
            return long(tag)
        if (tag == HproseTags.TagInteger or
            tag == HproseTags.TagLong):
            return self.__readLongWithoutTag()
        self.unexpectedTag(tag)
    def __readDoubleWithoutTag(self):
        return float(_readuntil(self.stream, HproseTags.TagSemicolon))
    def readDouble(self):
        tag = self.stream.read(1)
        if '0' <= tag <= '9':
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
        if tag == HproseTags.TagEmpty: return ''
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
            raise HproseException, 'Bad utf-8 encoding'
        s = ''.join(s)
        if Unicode:
            s = unicode(s, 'utf-8')
        return s
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
        s = ''.join(s)
        if Unicode:
            s = unicode(s, 'utf-8')
        return s
    def readStringWithoutTag(self):
        s = self.__readString()
        self.refer.set(s)
        return s
    def readString(self):
        tag = self.stream.read(1)
        if tag == HproseTags.TagNull: return None
        if tag == HproseTags.TagEmpty: return (Unicode and [u''] or [''])[0]
        if tag == HproseTags.TagUTF8Char: return self.__readUTF8CharWithoutTag()
        if tag == HproseTags.TagRef: return self.__readRef()
        if tag == HproseTags.TagString: return self.readStringWithoutTag()
        self.unexpectedTag(tag)
    def readGuidWithoutTag(self):
        u = UUID(self.stream.read(38))
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
        for _ in xrange(c): l.append(self.unserialize())
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
        for _ in xrange(c):
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
        for i in xrange(count): setattr(obj, fields[i], self.unserialize())
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
        fields = [self.readString() for _ in xrange(count)]
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
            if '0' <= tag <= '9':
                microsecond = microsecond + int(tag + self.stream.read(2), 10)
                tag = self.stream.read(1)
                if '0' <= tag <= '9':
                    self.stream.read(2)
                    tag = self.stream.read(1)
        return (tag, microsecond)
    def reset(self):
        del self.classref[:]
        self.refer.reset()

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
        if isinstance(val, str) or isinstance(val, unicode):
            self.ref[val] = self.refcount
        else:
            self.ref[id(val)] = self.refcount
        self.refcount += 1
    def write(self, val):
        if not (isinstance(val, str) or isinstance(val, unicode)):
            val = id(val)
        if (val in self.ref):
            self.stream.write('%c%d%c' % (HproseTags.TagRef,
                                          self.ref[val],
                                          HproseTags.TagSemicolon))
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
        self.refer = (simple and [FakeWriterRefer()] or [RealWriterRefer(stream)])[0]
    def serialize(self, v):
        if v == None: self.writeNull()
        elif isinstance(v, bool): self.writeBoolean(v)
        elif isinstance(v, int): self.writeInteger(v)
        elif isinstance(v, float): self.writeDouble(v)
        elif isinstance(v, long): self.writeLong(v)
        elif isinstance(v, str):
            if v == '':
                self.writeEmpty()
            elif Unicode:
                self.writeBytesWithRef(v)
            else:
                try:
                    self.writeStringWithRef(unicode(v, 'utf-8'))
                except ValueError:
                    self.writeBytesWithRef(v)
        elif isinstance(v, unicode):
            if v == u'':
                self.writeEmpty()
            elif len(v) == 1:
                self.writeUTF8Char(v)
            else:
                self.writeStringWithRef(v)
        elif isinstance(v, UUID): self.writeGuidWithRef(v)
        elif isinstance(v, (list, tuple)): self.writeListWithRef(v)
        elif isinstance(v, dict): self.writeMapWithRef(v)
        elif isinstance(v, (datetime.datetime, datetime.date)): self.writeDateWithRef(v)
        elif isinstance(v, datetime.time): self.writeTimeWithRef(v)
        elif isinstance(v, object): self.writeObjectWithRef(v)
        else: raise HproseException, 'Not support to serialize this data'
    def writeInteger(self, i):
        if 0 <= i <= 9:
            self.stream.write('%d' % (i,))
        else:
            self.stream.write('%c%d%c' % (HproseTags.TagInteger,
                                          i,
                                          HproseTags.TagSemicolon))
    def writeLong(self, l):
        if 0 <= l <= 9:
            self.stream.write('%d' % (l,))
        else:
            self.stream.write('%c%d%c' % (HproseTags.TagLong,
                                          l,
                                          HproseTags.TagSemicolon))
    def writeDouble(self, d):
        if isNaN(d): self.writeNaN()
        elif isInf(d): self.writeInfinity(isPosInf(d))
        else: self.stream.write('%c%s%c' % (HproseTags.TagDouble,
                                            d,
                                            HproseTags.TagSemicolon))
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
            if date.utcoffset() != ZERO and date.utcoffset() != None:
                date = date.astimezone(utc)
            if date.hour == 0 and date.minute == 0 and date.second == 0 and date.microsecond == 0:
                fmt = '%c%s' % (HproseTags.TagDate, '%Y%m%d')
            elif date.year == 1970 and date.month == 1 and date.day == 1:
                fmt = '%c%s' % (HproseTags.TagTime, '%H%M%S')
            else:
                fmt = '%c%s%c%s' % (HproseTags.TagDate, '%Y%m%d', HproseTags.TagTime, '%H%M%S')
            if date.microsecond > 0:
                fmt = '%s%c%s' % (fmt, HproseTags.TagPoint, '%f')
            if date.utcoffset() == ZERO:
                fmt = '%s%c' % (fmt, HproseTags.TagUTC)
            else:
                fmt = '%s%c' % (fmt, HproseTags.TagSemicolon)
        else:
            fmt = '%c%s%c' % (HproseTags.TagDate, '%Y%m%d', HproseTags.TagSemicolon)
        self.stream.write(date.strftime(fmt))
    def writeDateWithRef(self, date):
        if not self.refer.write(date): self.writeDate(date)
    def writeTime(self, time):
        self.refer.set(time)
        fmt = '%c%s' % (HproseTags.TagTime, '%H%M%S')
        if time.microsecond > 0:
            fmt = '%s%c%s' % (fmt, HproseTags.TagPoint, '%f')
        if time.utcoffset() == ZERO:
            fmt = '%s%c' % (fmt, HproseTags.TagUTC)
        else:
            fmt = '%s%c' % (fmt, HproseTags.TagSemicolon)
        self.stream.write(time.strftime(fmt))
    def writeTimeWithRef(self, time):
        if not self.refer.write(time): self.writeTime(time)
    def writeBytes(self, b):
        self.refer.set(b)
        length = len(b)
        if length == 0:
            self.stream.write('%c%c%c' % (HproseTags.TagBytes,
                                          HproseTags.TagQuote,
                                          HproseTags.TagQuote))
        else:
            self.stream.write('%c%d%c%s%c' % (HproseTags.TagBytes,
                                              length,
                                              HproseTags.TagQuote,
                                              b,
                                              HproseTags.TagQuote))
    def writeBytesWithRef(self, b):
        if not self.refer.write(b): self.writeBytes(b)
    def writeUTF8Char(self, u):
        self.stream.write('%c%s' % (HproseTags.TagUTF8Char, u.encode('utf-8')))
    def writeString(self, s):
        self.refer.set(s)
        length = len(s)
        if length == 0:
            self.stream.write('%c%c%c' % (HproseTags.TagString,
                                          HproseTags.TagQuote,
                                          HproseTags.TagQuote))
        else:
            self.stream.write('%c%d%c%s%c' % (HproseTags.TagString,
                                              length,
                                              HproseTags.TagQuote,
                                              s.encode('utf-8'),
                                              HproseTags.TagQuote))
    def writeStringWithRef(self, s):
        if not self.refer.write(s): self.writeString(s)
    def writeGuid(self, guid):
        self.refer.set(guid)
        self.stream.write(HproseTags.TagGuid)
        self.stream.write(HproseTags.TagOpenbrace)
        self.stream.write(str(guid))
        self.stream.write(HproseTags.TagClosebrace)
    def writeGuidWithRef(self, guid):
        if not self.refer.write(guid): self.writeGuid(guid)
    def writeList(self, l):
        self.refer.set(l)
        count = len(l)
        if count == 0:
            self.stream.write('%c%c' % (HproseTags.TagList,
                                        HproseTags.TagOpenbrace))
        else:
            self.stream.write('%c%d%c' % (HproseTags.TagList,
                                          count,
                                          HproseTags.TagOpenbrace))
            for i in xrange(count): self.serialize(l[i])
        self.stream.write(HproseTags.TagClosebrace)
    def writeListWithRef(self, l):
        if not self.refer.write(l): self.writeList(l)
    def writeMap(self, m):
        self.refer.set(m)
        count = len(m)
        if count == 0:
            self.stream.write('%c%c' % (HproseTags.TagMap,
                                        HproseTags.TagOpenbrace))
        else:
            self.stream.write('%c%d%c' % (HproseTags.TagMap,
                                          count,
                                          HproseTags.TagOpenbrace))
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
        self.stream.write('%c%d%c' % (HproseTags.TagObject,
                                      index,
                                      HproseTags.TagOpenbrace))
        self.refer.set(obj)
        data = vars(obj)
        count = len(fields)
        for i in xrange(count):
            self.serialize(data[fields[i]])
        self.stream.write(HproseTags.TagClosebrace)
    def writeObjectWithRef(self, obj):
        if not self.refer.write(obj): self.writeObject(obj)
    def __writeClass(self, classname, fields):
        length = len(unicode(classname, 'utf-8'))
        count = len(fields)
        if count == 0:
            self.stream.write('%c%d%c%s%c%c' % (HproseTags.TagClass,
                                                length,
                                                HproseTags.TagQuote,
                                                classname,
                                                HproseTags.TagQuote,
                                                HproseTags.TagOpenbrace))
        else:
            self.stream.write('%c%d%c%s%c%d%c' % (HproseTags.TagClass,
                                                  length,
                                                  HproseTags.TagQuote,
                                                  classname,
                                                  HproseTags.TagQuote,
                                                  count,
                                                  HproseTags.TagOpenbrace))
            for i in xrange(count):
                field = unicode(fields[i], 'utf-8')
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
        stream = StringIO()
        writer = HproseWriter(stream, simple)
        writer.serialize(v)
        return stream.getvalue()
    serialize = staticmethod(serialize)

    def unserialize(s, simple = False):
        stream = StringIO(s)
        reader = HproseReader(stream, simple)
        return reader.unserialize()
    unserialize = staticmethod(unserialize)
