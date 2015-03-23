#!/usr/bin/env python
# encoding: utf-8

import hprose

class MyFilter(object):
    def inputFilter(self, data, context):
        print(data)
        return data
    def outputFilter(self, data, context):
        print(data)
        return data

def main():
    client = hprose.HttpClient('http://127.0.0.1:8181/')
    client.filter = MyFilter()
    print(client.send_data({"Mon": 1, "Tue": 2, "Wed": { "i1": "Wed", "i2": 5} }))

if __name__ == '__main__':
    main()
