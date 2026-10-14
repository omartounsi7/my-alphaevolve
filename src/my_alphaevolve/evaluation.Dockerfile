# The image in which DockerEvaluator runs the programs written by the LLM.
# The my_alphaevolve package and the problem's folder are mounted at run time, read-only.
FROM python:3.12-slim

# The packages programs may import: the problem's requirements.txt, possibly empty.
COPY requirements.txt /tmp/requirements.txt
RUN if [ -s /tmp/requirements.txt ]; then \
        pip install --no-cache-dir --disable-pip-version-check --root-user-action=ignore \
            --requirement /tmp/requirements.txt; \
    fi \
    && rm /tmp/requirements.txt

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8

# "nobody": a user without any rights.
USER 65534:65534
WORKDIR /tmp
