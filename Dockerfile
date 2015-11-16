FROM gliderlabs/alpine:3.1

WORKDIR /app
COPY . /app
RUN apk --update add --virtual build-dependencies \
    python-dev \
    py-pip \
    build-base \
    curl \
    && pip install virtualenv \
    && virtualenv /env \
	&& curl -s -k -o /tmp/sdk.tar.gz 'https://dl.dropboxusercontent.com/u/165239/mcn_cc_sdk.tgz' \
	&& /env/bin/pip install /tmp/sdk.tar.gz \
	&& curl -s -k -o /tmp/sm.tar.gz 'https://dl.dropboxusercontent.com/u/165239/sm-0.4.tgz' \
	&& /env/bin/pip install /tmp/sm.tar.gz \
	&& /env/bin/pip install -r /app/requirements.txt \
	&& /env/bin/python setup.py install \
    && rm -rf /var/cache/apk/* /root/.cache/* /tmp/*
EXPOSE 8080
CMD ["/env/bin/python", "./wsgi/application"]