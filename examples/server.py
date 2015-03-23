#!/usr/bin/env python
# encoding: utf-8

import hprose

def hello(name):
	return 'Hello %s!' % name

def main():
	server = hprose.HttpServer(port = 8181)
	server.addFunction(hello)
	server.start()

if __name__ == '__main__':
	main()
