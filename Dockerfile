FROM centos:7
WORKDIR /opt/code
COPY ./ /opt/code

RUN yum update -y \
    && yum install -y https://centos7.iuscommunity.org/ius-release.rpm \
    && yum install -y python36u python36u-libs python36u-devel python36u-pip \
    && yum install -y which gcc \ 
    && yum install -y openldap-devel  

EXPOSE 8080
ENTRYPOINT python3 httpd.py --host=0.0.0.0

CMD ["--port=8080", "--workers=10", "--doc_root=/www/http-test-suite/"]