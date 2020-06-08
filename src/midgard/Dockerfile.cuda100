FROM meadml/cuda10.0-cudnn7-devel-ubuntu16.04-python3.6

RUN apt-get update && \
    apt-get install -y g++ make git vim wget software-properties-common tmux ssh

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/

RUN pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app

EXPOSE 29999

ENTRYPOINT ["python3.6"]

CMD ["-m", "midgard.server"]
