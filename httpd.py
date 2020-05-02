import socket
import os
import logging
import multiprocessing
import mimetypes
import argparse
from datetime import datetime


SOCKET_TIMEOUT = 10
RECONNECT_MAX_ATTEMPTS = 5
RECONNECT_DELAY = 10
PACKET_SIZE = 1024
HOST = '127.0.0.1'
PORT = 8080
DOCUMENT_ROOT = './DOCUMENT_ROOT/'
SERVER_NAME = 'HTTPServer'

class TCPServer:

    address_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    sol_socket = socket.SOL_SOCKET
    so_reuseaddr = socket.SO_REUSEADDR
    request_queue_size = 5

    def __init__(self, host, port, doc_root,
                socket_timeout=SOCKET_TIMEOUT,
                reconnect_max_attempts=RECONNECT_MAX_ATTEMPTS,
                reconnect_delay=RECONNECT_DELAY,
                connect_now=True):
        
        self.host = host
        self.port = port
        self.doc_root = doc_root
        self.socket_timeout = socket_timeout
        self.reconnect_delay = reconnect_delay
        self.reconnect_max_attempts = reconnect_max_attempts
        self.socket = socket.socket(self.address_family, self.socket_type)

    def server_bind(self):
        self.socket.bind((self.host, self.port))
        self.socket.setsockopt(self.sol_socket, self.so_reuseaddr, 1)
        self.server_address = self.socket.getsockname()

    def server_activate(self):
        self.socket.listen(self.request_queue_size)

    def get_request(self):
        """Get the request and client address from the socket.
        May be overridden.
        """
        return self.socket.accept()

    def shutdown_request(self, request):
        """Called to shutdown and close an individual request."""
        try:
            #explicitly shutdown.  socket.close() merely releases
            #the socket and waits for GC to perform the actual close.
            request.shutdown(socket.SHUT_WR)
        except socket.error:
            pass #some platforms may raise ENOTCONN here
        request.close()


    def server_close(self):
        """Called to clean-up the server.
        May be overridden.
        """
        self.socket.close()

    def start(self):
        self.server_bind()
        self.server_activate()

    def run_forever(self):
        while True:
            conn, addr = self.get_request()
            data = conn.recv(PACKET_SIZE)
            if data:
                response = self.handle_request(data)
                conn.sendall(response)
            else:
                logging.info("No data recieved from {}".format(addr))
            conn.close()

    def handle_request(self, data):
        return data


class HTTPRequest:

    def __init__(self, data):
        self.data = data.decode()
        self.headers = {}

    def parse(self):
        lines = self.data.split('\r\n')
        request_line = lines[0]
        self._parse_request_line(request_line)
        for field in lines[1:]:
            logging.info("Field {}".format(field))
            try:
                key, value = field.split(': ')
                self.headers[key] = value
            except ValueError as e:
                logging.error("{0} for value {1}".format(e,field))

    def _parse_request_line(self, line):
        words = line.split(' ')
        self.method = words[0]
        self.uri = words[1]

        if len(words) > 1:
            self.http_version = words[2]


class HTTPResponse:

    status_codes = {
        200: 'OK',
        404: 'Not found', 
        403: 'Forbidden',
        405: 'Invalid request',
    }

    def __init__(self, request):
        self.method = request.method
        self.uri = request.uri
        self.headers = request.headers

    def process_request(self, doc_root):
        if self.method in ["GET", "HEAD"]:
            path = self.uri.strip('/')
            filename = doc_root + 'index.html' if path == '' else doc_root + path
            if os.path.exists(filename):
                response_line = self.response_line(200)
                contenet_type = mimetypes.guess_type(filename)[0] or 'text/html'
                content_lenght = os.path.getsize(filename)
                extra_headers = {'Content-Type': contenet_type, 
                                'Content-Length': content_lenght}
                response_headers = self.response_headers(extra_headers)
                with open(filename, 'rb') as filename_to_open:
                    response = filename_to_open.read()
                response_body = response
            else:
                response_line = self.response_line(404)
                response_headers = self.response_headers()
                response_body = "<h1>404 Not Found</h1>".encode()
            
            if self.method == 'GET': 
                response = "".join((response_line, response_headers, '\r\n')).encode() + response_body
            elif self.method == "HEAD":
                response = "".join((response_line, response_headers, '\r\n')).encode()
            return response
        else:
            response_line = self.response_line(status_code=501)
            response_headers = self.response_headers()
            blank_line = "\r\n"
            response_body = "<h1>405 Not Implemented</h1>"
            return ','.join(list((response_line, 
                              response_headers, 
                              blank_line, 
                              response_body
                              )))

    def response_line(self, status_code):
        """Returns response line"""
        reason = self.status_codes[status_code]
        return "HTTP/1.1 {} {}\r\n".format(status_code, reason)

    def response_headers(self, extra_headers=None):
        """Returns headers
        The `extra_headers` can be a dict for sending 
        extra headers for the current response
        """
        headers_copy = self.headers.copy()
        if extra_headers:
            headers_copy.update(extra_headers)

        response_headers = {}
        response_headers['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S')
        response_headers['Connection'] = headers_copy.get('Connection', None)
        response_headers['Server'] = SERVER_NAME
        response_headers['Content-Length'] = headers_copy.get('Content-Length', None)
        response_headers['Content-Type'] = headers_copy.get('Content-Type', None)

        return ''.join(["%s: %s\r\n" % (key, value) for (key, value) in response_headers.items()])
        #return '\r\n'.join('{}: {}'.format(k, v) for k, v in response_headers.items())
        #return '\r\n'.join('{}:{}'.format(k,v) for k, v in response_headers.items())



class HTTPServer(TCPServer):

    def handle_request(self, data):
        """Handles the incoming request.
        Compiles and returns the response
        """
        worker_id = os.getpid()
        try:
            request = HTTPRequest(data)
            request.parse()
            response = HTTPResponse(request)
            logging.info('[Worker {}] Processing request'.format(
                worker_id,
            ))
            return response.process_request(self.doc_root)
        except Exception:
            logging.exception('[Worker {}] Error while sending request to'.format(
                worker_id,
            ))



def run_server(host, port, workers, doc_root):
    '''
    Run server and start workers
    Once a client has connected, a new thread will be inititated to handle intereaction between
    the server and the client.
    '''
    logging.info('Staring server on at {0}:{1}'.format(host, port))
    server = HTTPServer(host, port, doc_root)
    server.start()

    processses = []
    try:
        for _ in range(workers):
            communication_server = multiprocessing.Process(target=server.run_forever, args=())
            processses.append(communication_server)
            # communication_server.daemon = True
            communication_server.start()
            logging.debug("Worker started")
    except KeyboardInterrupt:
        for process in processses:
            if process:
                process.terminate()

def set_logger(debug=True):
    '''
    Setup logger configuration
    '''
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, 
                        format='[%(asctime)s] %(levelname).1s %(message)s', 
                        datefmt='%Y.%m.%d %H:%M:%S')


def parse_elements():
    parser = argparse.ArgumentParser(description='Read cofing')
    parser.add_argument('-s', '--host', default=HOST, help='Host')
    parser.add_argument('-p', '--port', default=PORT, help='Port')
    parser.add_argument('-w', '--workers', default=1, required=False,  help='Number of worker')
    parser.add_argument('-r', '--doc_root', default=DOCUMENT_ROOT, help='Documnets root')
    return parser.parse_args()

def set_doc_root(doc_root):
    return doc_root if os.path.exists(doc_root) else DOCUMENT_ROOT

if __name__ == '__main__':
    args = parse_elements()
    set_logger(debug=False)
    doc_root = set_doc_root(args.doc_root)
    run_server(args.host, args.port, args.workers, doc_root)