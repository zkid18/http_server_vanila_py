import socket
import os
import logging
import multiprocessing
import mimetypes
import argparse
from datetime import datetime
import urllib.parse



SOCKET_TIMEOUT = 30
RECONNECT_MAX_ATTEMPTS = 5
RECONNECT_DELAY = 10
PACKET_SIZE = 1024
HOST = '127.0.0.1'
PORT = 8080
DOCUMENT_ROOT = './www/'
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
                if response:
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
        self.method = None
        self.uri = None
        self.args = {}
        self.http_version = None

    def parse(self):
        lines = self.data.split('\r\n')
        request_line = lines[0]
        if request_line != '\n':
            logging.debug("Request line {}".format(request_line))
            self._parse_request_line(request_line)
            for field in lines[1:]:
                logging.debug("Field {}".format(field))
                try:
                    key, value = field.split(': ')
                    self.headers[key] = value
                except ValueError as e:
                    logging.error("{0} for value {1}".format(e,field))

    def _parse_request_line(self, line):
        words = line.split(' ')
        self.method = words[0]
        req = words[1].split('?')
        # self.uri = req[0].replace('%20', ' ')
        self.uri = urllib.parse.unquote(req[0])
        
        if len(req) > 2:
            raw_args = req[0].split['&']
            self.args = {arg.split('=')[0]:arg.split('=')[1] for arg in raw_args}

        if len(words) > 1:
            self.http_version = words[2]


class HTTPResponse:

    status_codes = {
        200: 'OK',
        400: 'Bad request',
        404: 'Not found', 
        403: 'Forbidden',
        405: 'Invalid request',
    }

    def __init__(self, request):
        self.method = request.method
        self.uri = request.uri
        self.headers = request.headers

    def process_request(self, doc_root):
        if (self.method is None):
            response_line = self.response_line(status_code=400)
            response_headers = self.response_headers()
            response = "".join((response_line, response_headers, '\r\n')).encode()
            return response

        if self.method in ["GET", "HEAD"]:
            if self.uri.startswith("/"):
                path = doc_root+ self.uri[1:]
            if self.uri == '':
                filename = doc_root + 'index.html'
            elif (os.path.isdir(path)):                    
                if not path.endswith('/'):
                    path += '/'
                filename = path + 'index.html'
            else:
                filename = path

            if self._is_directory_traversal(doc_root, filename):
                logging.info("Directory traversal attack")
                response_line = self.response_line(403)
                response_headers = self.response_headers()
                response_body = "<h1>403 Forbidden</h1>".encode()         

            elif os.path.exists(filename):
                logging.debug("Filename {} exist".format(filename))
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
                logging.debug("Filename {} doesn't exist".format(filename))
                response_line = self.response_line(404)
                response_headers = self.response_headers()
                response_body = "<h1>404 Not Found</h1>".encode()                 
            
            if self.method == 'GET': 
                response = "".join((response_line, response_headers, '\r\n')).encode() + response_body
            elif self.method == "HEAD":
                response = "".join((response_line, response_headers, '\r\n')).encode()
            return response
        else:
            response_line = self.response_line(status_code=405)
            response_headers = self.response_headers()
            response_body = "<h1>405 Not Implemented</h1>".encode()
            response = "".join((response_line, response_headers, '\r\n')).encode() + response_body
            return response

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

    def _is_directory_traversal(self, doc_root, filename):
        route = filename.split("/..")
        logging.debug("Route {}".format(route))
        if len(route) > 1:
            route_path = route[0]
            current_directory = os.path.abspath(doc_root+route_path)
            requested_path = os.path.relpath(filename, start=current_directory)
            common_prefix = os.path.commonprefix([requested_path, current_directory])
            logging.debug("Common prefix {}".format(common_prefix))
            logging.debug("Current directory {}".format(current_directory))
            has_dir_traversal = common_prefix != current_directory
            has_dir_traversal = requested_path.startswith(os.pardir)
            return has_dir_traversal
        return False


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
            logging.info('[Worker {0}] Processing request {1} to {2}'.format(
                worker_id, request.method, request.uri
            ))
            return response.process_request(self.doc_root)
        except Exception:
            logging.exception('[Worker {0}] Error while sending request'.format(
                worker_id
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
    parser.add_argument('-p', '--port', type=int, default=PORT, help='Port')
    parser.add_argument('-w', '--workers', type=int, default=1, required=False,  help='Number of worker')
    parser.add_argument('-r', '--doc_root', default=DOCUMENT_ROOT, help='Documnets root')
    return parser.parse_args()

def set_doc_root(doc_root):
    if os.path.exists(doc_root):
        logging.debug("Document root {} exist".format(doc_root))
        return doc_root
    else:
        logging.debug("Document root {} doesn't exist".format(doc_root))
        return DOCUMENT_ROOT

if __name__ == '__main__':
    args = parse_elements()
    set_logger(debug=True)
    logging.info(args.doc_root)
    doc_root = set_doc_root(args.doc_root)
    run_server(args.host, args.port, args.workers, doc_root)