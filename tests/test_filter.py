# encoding: utf-8

from gzip import GzipFile

from unittest import TestCase

from marrow.util.compat import IO, unicode
from marrow.wsgi.egress.compression import CompressionFilter



_status = b"200 OK"
_body = b"a" * 1000


class TestCompressionFilter(TestCase):
    def setUp(self):
        self.filter = CompressionFilter()
    
    def mock_headers(self, length=None, disable=False, mime=b"text/plain"):
        headers = [(b'Content-Type', mime)] if mime else []
        
        if length is not None:
            headers.append((b'Content-Length', unicode(length).encode('ascii')))
        
        if disable:
            headers.append((b'Content-Encoding', b'mock'))
        
        return headers
    
    def mock_environ(self, enable=True, disable=False, async=False):
        environ = {
                'wsgi.multiprocess': False,
                'wsgi.multithread': False,
                'wsgi.run_once': True,
                'wsgi.version': (2, 0),
            }
        
        if enable:
            environ['HTTP_ACCEPT_ENCODING'] = b'gzip'
        
        if disable:
            environ['wsgi.compression'] = False
        
        if async:
            environ['wsgi.async'] = True
        
        return environ
    
    def find(self, header, headers):
        """Determine the value and index into headers for the given header, or None if not found."""
        
        for i, (name, value) in enumerate(headers):
            if name.lower() == header:
                return value, i
        
        return None, None
    
    def decompress(self, body):
        buf = IO()
        
        for chunk in body:
            buf.write(chunk)
        
        buf.seek(0)
        
        gzfile = GzipFile(mode='rb', fileobj=buf)
        data = gzfile.read()
        gzfile.close()
        
        del buf
        del gzfile
        
        return data
    
    def test_functional(self):
        _, headers, body = self.filter(self.mock_environ(), _status, self.mock_headers(len(_body)), [_body])
        assert int(self.find(b'content-length', headers)[0]) < len(_body), "Content didn't shrink."
        self.assertEquals(_body, self.decompress(body))
        
        _, headers, body = self.filter(self.mock_environ(async=True), _status, self.mock_headers(len(_body)), [_body])
        self.assertEquals(_body, self.decompress(body))
    
    def test_disabled(self):
        _, headers, body = self.filter(self.mock_environ(disable=True), _status, self.mock_headers(len(_body)), [_body])
        self.assertEquals(_body, b''.join(body))
        
        def gen():
            yield _body
        
        _, headers, body = self.filter(self.mock_environ(async=True), _status, self.mock_headers(len(_body)), gen)
        self.assertEquals(_body, b''.join(body()))
        
        _, headers, body = self.filter(self.mock_environ(enable=False), _status, self.mock_headers(len(_body)), [_body])
        self.assertEquals(_body, b''.join(body))
        
        _, headers, body = self.filter(self.mock_environ(), _status, self.mock_headers(len(_body), disable=True), [_body])
        self.assertEquals(_body, b''.join(body))
    
    def test_mimetypes(self):
        _, headers, body = self.filter(self.mock_environ(), _status, self.mock_headers(len(_body), mime=None), [_body])
        self.assertEquals(_body, b''.join(body))
        
        _, headers, body = self.filter(self.mock_environ(), _status, self.mock_headers(len(_body), mime=b"application/gzip"), [_body])
        self.assertEquals(_body, b''.join(body))
        
        _, headers, body = self.filter(self.mock_environ(), _status, self.mock_headers(len(_body), mime=b'video/mpeg4'), [_body])
        self.assertEquals(_body, b''.join(body))
    
    def test_inefficient(self):
        _, headers, body = self.filter(self.mock_environ(), _status, self.mock_headers(1), [b'a'])
        assert int(self.find(b'content-length', headers)[0]) > 1, "Content didn't grow in size."
        self.assertEquals(b'a', self.decompress(body))
    
    def test_edge(self):
        _, headers, body = self.filter(self.mock_environ(), _status, self.mock_headers(), [_body])
        self.assertEquals(_body, self.decompress(body))
        self.assertNotEqual((None, None), self.find(b'content-length', headers))
