FROM python:3.6.4-jessie

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/

RUN pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app

# Install baseline
RUN python3.6 -m pip install mead-baseline


EXPOSE 9003

ENTRYPOINT ["python", "-m", "swagger_server"]
