# jessie wasn't able to use apt-get
FROM python:3.6.4-stretch

# Install tools
RUN apt-get update && \
    apt-get install -y wget ssh && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /src/*.deb

########################################################################
# Install Git-LFS
ADD https://github.com/git-lfs/git-lfs/releases/download/v2.7.1/git-lfs-linux-amd64-v2.7.1.tar.gz /opt/git-lfs/git-lfs.tar.gz
RUN cd /opt/git-lfs && \
    tar -xzvf /opt/git-lfs/git-lfs.tar.gz && \
    ./install.sh && \
    git lfs install
########################################################################

RUN python3.6 -m pip install --upgrade pip && \
    python3.6 -m pip install setuptools && \
    python3.6 -m pip install pytest 

# Copy project over
WORKDIR /usr/odin

# we copy the deps first so that we can have a cached layer
# that only gets updated when they change
COPY setup.py ./setup.py
COPY odin/version.py ./odin/version.py
COPY . .
# this layer should get cached, making builds faster
RUN python3.6 -m pip install .

# Install baseline
RUN python3.6 -m pip install mead-baseline && python3.6 -m pip install mead-xpctl-client

# Install hpctl
ADD https://github.com/mead-ml/hpctl/archive/master.tar.gz /usr/odin/hpctl-master.tar.gz
RUN tar xzf hpctl-master.tar.gz && \
    cd ./hpctl-master/ && \
    pip install -e .

RUN python3.6 -m pip install pylint
#RUN pylint --persistent=n ./odin

# TODO run tests/etc.
RUN pytest /usr/odin/tests
# Set terminal encodings
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
# Set ENV to where nest is

ENTRYPOINT ["odin-serve"]
