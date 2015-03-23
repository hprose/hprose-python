#!/usr/bin/env python
# encoding: utf-8

import hprose

def send_data(data):
    print(data)
    return data

def main():
    server = hprose.HttpServer(port = 8181)
    server.debug = True
    server.addFunction(send_data)
    server.start()

if __name__ == '__main__':
    main()
