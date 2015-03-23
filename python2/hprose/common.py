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
# hprose/common.py                                         #
#                                                          #
# hprose common for python 2.3+                            #
#                                                          #
# LastModified: Mar 19, 2014                               #
# Author: Ma Bingyao <andot@hprose.com>                    #
#                                                          #
############################################################

class HproseResultMode:
    Normal = 0
    Serialized = 1
    Raw = 2
    RawWithEndTag = 3

class HproseException(Exception):
    pass

class HproseFilter(object):
    def inputFilter(self, data, context):
        return data;
    def outputFilter(self, data, context):
        return data;