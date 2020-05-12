FROM python:3.6.7
WORKDIR /code
COPY ./*.py ./

EXPOSE 8080
CMD ["python3", "httpd.py", "--host=localhost", "--port=8080", "--workers=5", "--doc_root=/www"]