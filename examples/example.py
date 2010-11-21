import logging
from marrow.server.http import HTTPServer
from marrow.wsgi.egress.compression import CompressionFilter



def hello(request):
    return b'200 OK', [(b'Content-Type', b'text/plain'), (b'Content-Length', b'100')], [b'a' * 100]


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    
    server = HTTPServer(None, 8080, application=hello, egress=[CompressionFilter(level=1)])
    server.start()
