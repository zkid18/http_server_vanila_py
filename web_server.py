import socket

class TCPServer:

    def __init__(self):
        self.host = '127.0.0.1'
        self.port = 8080

    def start(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        s.bind((self.host, self.port))
        s.listen(5)

        print("Listening at", s.getsockname())

        while True:
            conn, addr = s.accept()
            print("Connected by", addr)
            data = conn.recv(1024)
            response = self.handle_request(data)
            conn.sendall(response)
            conn.close()

    def handle_request(self, data):
        return data

class HTTPServer(TCPServer):
    def handle_request(self, data):
        return "Request received!".encode()

if __name__ == '__main__':
    server = HTTPServer()
    server.start()