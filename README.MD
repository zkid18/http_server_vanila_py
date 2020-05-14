# OTUServer
HTTP server with implemented GET and HEAD methods.
N workers (processes) from multiprocessing module. Each worker accepts requests concurrently, then process it and generate response.

Server can:

- Scale to multiple workers
- The number of workers specified in ‑w command line argument
- Return 200, 403 or 404 for GET and HEAD requests
- Return 405 for other requests
- Return files to an arbitrary path in DOCUMENT_ROOT
- /file.html should return the content DOCUMENT_ROOT/file.html
- DOCUMENT_ROOT is specified in ‑r command line argument
- Return index.html as directory index
- /directory/ should return DOCUMENT_ROOT/directory/index.html
- Return the following headers for successful GET requests: Date, Server, Content-Length, Content-Type, Connection
- Correct Content‑Type for: .html, .css, .js, .jpg, .jpeg, .png, .gif, .swf
- Understand spaces and %XX in file names

## Requirements
Python 3.x

## Validation

0. Unit tests

To run the test:
```
python3 httpd.py --doc_root ./www/http-test-suite/
python3 httptest.py 
```
 
```
directory index file exists ... ok
document root escaping forbidden ... ok
Send bad http headers ... ok
file located in nested folders ... ok
absent file returns 404 ... ok
urlencoded filename ... ok
file with two dots in name ... ok
query string after filename ... ok
filename with spaces ... ok
Content-Type for .css ... ok
Content-Type for .gif ... ok
Content-Type for .html ... ok
Content-Type for .jpeg ... ok
Content-Type for .jpg ... ok
Content-Type for .js ... ok
Content-Type for .png ... ok
Content-Type for .swf ... ok
head method support ... ok
directory index file absent ... ok
large file downloaded correctly ... ok
post method forbidden ... ok
Server header exists ... ok

----------------------------------------------------------------------
Ran 22 tests in 0.271s

OK
```

1. Show wikipedia Russia page
```
python3 httpd.py --doc_root ./www/http-test-suite/
http://127.0.0.1:8080/httptest/wikipedia_russia.html
````

2. Load testing
Test in CentOS 
`docker build --tag http_server:1.0 .`
`docker run --publish 8081:8080 --name bb http_server:1.0 --port=8080 --workers=4`
`ab -n 50000 -c 100 -s 9999 -r http://127.0.0.1:8081`

```
Benchmarking 127.0.0.1 (be patient)
Completed 5000 requests
Completed 10000 requests
Completed 15000 requests
Completed 20000 requests
Completed 25000 requests
Completed 30000 requests
Completed 35000 requests
Completed 40000 requests
Completed 45000 requests
Completed 50000 requests
Finished 50000 requests


Server Software:        HTTPServer
Server Hostname:        127.0.0.1
Server Port:            8081

Document Path:          /
Document Length:        161 bytes

Concurrency Level:      100
Time taken for tests:   963.490 seconds
Complete requests:      49994
Failed requests:        227
   (Connect: 0, Receive: 0, Length: 227, Exceptions: 0)
Total transferred:      14780799 bytes
HTML transferred:       8012487 bytes
Requests per second:    51.89 [#/sec] (mean)
Time per request:       1927.212 [ms] (mean)
Time per request:       19.272 [ms] (mean, across all concurrent requests)
Transfer rate:          14.98 [Kbytes/sec] received

Connection Times (ms)
              min  mean[+/-sd] median   max
Connect:        0   16 361.2      3   22190
Processing:     4 1307 10140.8     51  228237
Waiting:        0  687 3746.5     49  116763
Total:          7 1323 10148.5     55  228279

Percentage of the requests served within a certain time (ms)
  50%     55
  66%     76
  75%    100
  80%    143
  90%   1257
  95%   3150
  98%   7694
  99%  17266
 100%  228279
```

