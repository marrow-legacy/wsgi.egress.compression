# encoding: utf-8

"""Egress content filtering extension for GZip compression of content.

This should be the last filter, as the body is no longer parseable once the filter has run.

Better yet, this type of compression should be implemented in a front-end load balancer like Apache or Nginx.

Usage example:

    import logging
    from marrow.server.http import HTTPServer
    from marrow.wsgi.egress.compression import CompressionFilter
    
    logging.basicConfig(level=logging.DEBUG)
    
    def hello(request):
        return b'200 OK', [(b'Content-Type', b'text/plain'), (b'Content-Length', b'100')], [b'a' * 100]
    
    server = HTTPServer(None, 8080, application=hello, egress=[CompressionFilter(level=6)])
    server.start()

"""


from gzip import GzipFile

from marrow.util.compat import binary, unicode, IO

from functools import partial


__all__ = ['CompressionFilter']
log = __import__('logging').getLogger(__name__)



class CompressionFilter(object):
    def __init__(self, level=6):
        self.level = level
        
        super(CompressionFilter, self).__init__()
    
    def __call__(self, request, status, headers, body):
        """Compress, if able, the response.
        
        This has the side effect that if your application does not declare a content-length, this filter will.
        """
        
        # TODO: Remove some of this debug logging; it'll slow things down and isn't really needed.
        
        if request.get('wsgi.compression', True) == False:
            log.debug("Bypassing compression at application's request.")
            return status, headers, body
        
        if request.get('wsgi.async') and hasattr(body, '__call__'):
            log.debug("Can not compress async responses, returning original response.")
            return status, headers, body
        
        if b'gzip' not in request.get('HTTP_ACCEPT_ENCODING', b''):
            log.debug("Browser support for GZip encoding not found, returning original response.")
            return status, headers, body
        
        def find(header):
            """Determine the value and index into headers for the given header, or None if not found."""
            
            for i, (name, value) in enumerate(headers):
                if name.lower() == header:
                    return value, i
            
            return None, None
        
        if find(b'content-encoding')[0]:
            log.debug("Content encoding already defined, returning original response.")
            return status, headers, body
        
        ctype, ctypeidx = find(b'content-type')
        
        if not ctype or not ctype.startswith((b'text/', b'application/')) or b'zip' in ctype:
            log.debug("Encountered uncompressable Content-Type (%s), returning original response.", ctype)
            return status, headers, body
        
        clength, clengthidx = find(b'content-length')
        
        headers.append((b"Content-Encoding", b'gzip'))
        
        # We have to read the entire body into a buffer before we can compress it.
        # This is because we need to determine the final Content-Length.
        # TODO: If the Content-Length is > 4MiB, we should use a tmpfile on-disk instead!
        
        buf = IO()
        compressed = GzipFile(mode='wb', compresslevel=self.level, fileobj=buf)
        
        for chunk in body:
            compressed.write(chunk)
        
        compressed.close()
        del compressed
        length = buf.tell()
        buf.seek(0)
        
        if clength:
            clength = int(clength)
            log.debug("Content-Length: %d - Compressed: %d - Savings: %d (%d%%)", clength, length, clength - length, length * 100 // clength)
        
            if length > int(clength):
                log.warn("Compression increased size of response!")
        
        length = (b'Content-Length', unicode(length).encode('ascii'))
        
        if clength: headers[clengthidx] = length
        else: headers.append(length)
        
        return status, headers, iter(partial(buf.read, 4096), b'')
