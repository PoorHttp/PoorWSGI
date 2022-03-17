# vim: ft=dockerfile
FROM python:3.8-buster

# instalace behovych a cast testovych zavislosti
RUN \
    apt-get update && \
    apt-get install --yes --no-install-recommends \
        curl \
        vim \
        sudo

ARG USER

RUN echo "#${USER} ALL=(ALL) ALL" > /etc/sudoers.d/docker-owner


ARG PKG_DIR

RUN pip3 install --find-links=file:///tmp \
        pytest mock-import pytest-pylint pytest-doctestplus openapi_core

EXPOSE 8000

ENV LC_ALL C.UTF-8
