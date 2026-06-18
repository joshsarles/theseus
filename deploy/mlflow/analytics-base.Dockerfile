FROM python:3.12-slim
# FROM registry1.dso.mil/opensource/python:v3.12

# not needed if using Iron Bank container
RUN groupadd -g 1001 python && \
    useradd -u 1001 -g 1001 -d /home/python python
RUN mkdir /home/python && \
    chmod -R 0755 /home/python && \
    chown -R python:python /home/python

# setup python packages for edge analytics
USER 1001
WORKDIR /home/python
COPY --chmod=0644 requirements_torch.txt .
RUN python -m venv .venv && \
    .venv/bin/pip install -U pip && \
    .venv/bin/pip install -r requirements_torch.txt --index-url https://download.pytorch.org/whl/cpu

COPY --chmod=0644 requirements.txt .
RUN .venv/bin/pip install -r requirements.txt

ENV VIRTUAL_ENV=/home/python/.venv/bin
ENV PATH="$VIRTUAL_ENV:$PATH"

ENTRYPOINT []