FROM python:3.6.4-jessie

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/

RUN pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app

# Docker ADD supports fetching from URIs, so we'll use that
ADD https://github.com/dpressel/mead-baseline/archive/master.tar.gz /usr/src/app/mead-baseline-master.tar.gz
RUN tar xzf mead-baseline-master.tar.gz && \
     cd ./mead-baseline-master/python && \
     pip install -e .[test,yaml]

EXPOSE 9003

ENTRYPOINT ["python", "-m", "swagger_server"]
