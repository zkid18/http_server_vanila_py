import socket
import os

SOCKET_TIMEOUT = 10
RECONNECT_MAX_ATTEMPTS = 5
RECONNECT_DELAY = 10
PACKET_SIZE = 1024
HOST = '127.0.0.1'
PORT = 8080


class TCPServer:

    address_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    request_queue_size = 5

    def __init__(self, host, port,
                socket_timeout=SOCKET_TIMEOUT,
                reconnect_max_attempts=RECONNECT_MAX_ATTEMPTS,
                reconnect_delay=RECONNECT_DELAY,
                connect_now=True):
        
        self.host = host
        self.port = port
        self.socket_timeout = socket_timeout
        self.reconnect_delay = reconnect_delay
        self.reconnect_max_attempts = reconnect_max_attempts
        self.socket = socket.socket(self.address_family, self.socket_type)


    def server_bind(self):
        self.socket.bind((self.host, self.port))
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

        while True:
            conn, addr = self.get_request()
            data = conn.recv(PACKET_SIZE)
            if data:
                response = self.handle_request(data)
                conn.sendall(response.encode())
            else:
                print("no more data from {}".format(addr))
            conn.close()

    def handle_request(self, data):
        return data


class HTTPRequest:

    def __init__(self, data):
        self.method = None
        self.uri = None
        self.http_version = '1.1'
        self.headers = {}
        self.parse(data.decode())

    def parse(self, data):
        lines = data.split('\r\n')
        request_line = lines[0]
        self.parse_request_line(request_line)

    def parse_request_line(self, line):
        words = line.split(' ')
        self.method = words[0]
        self.uri = words[1]

        if len(words) > 1:
            self.http_version = words[2]


class HTTPServer(TCPServer):

    status_codes = {
        200: 'OK',
        400: 'Bad request',
        404: 'Not found', 
        403: 'Forbidden',
        422: 'Invalid request',
        500: 'Internal error'
    }

    headers = {
        'Server': 'CrudeServer',
        'Content-Type': 'text/html',
    }

    def handle_request(self, data):
        """Handles the incoming request.
        Compiles and returns the response
        """
        request = HTTPRequest(data)
        try:
            '''
            TODO: OPTIONS and POST handling
            '''
            handler = getattr(self, 'handle_{}'.format(request.method))
        except AttributeError:
            handler = self.HTTP_501_handler
        response = handler(request)
        return response


    def handle_GET(self, request):
        filename = request.uri.strip('/')
        if os.path.exists(filename):
            response_line = self.response_line(200)
            response_headers = self.response_headers()
            response_body = "<h1>200 OK</h1>"
            
        else:
            response_line = self.response_line(404)
            response_headers = self.response_headers()
            response_body = "<h1>404 Not Found</h1>"

        response = (response_line, response_headers, '\r\n', response_body)
        return "".join(response)


    def HTTP_501_handler(self, request):
        response_line = self.response_line(status_code=501)
        response_headers = self.response_headers()
        blank_line = "\r\n"
        response_body = "<h1>501 Not Implemented</h1>"
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

        headers = ""

        for h in self.headers:
            headers += "{}:{}\r\n".format(h, self.headers[h])
        return headers

if __name__ == '__main__':
    server = HTTPServer(HOST, PORT)
    server.start()