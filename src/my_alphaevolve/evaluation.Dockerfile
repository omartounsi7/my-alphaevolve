# The image in which DockerEvaluator runs the programs written by the LLM.
# The my_alphaevolve package and the problem's folder are mounted at run time, read-only.
FROM python:3.12-slim

# Packages that programs may import will be installed here (issue #24).

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8

# "nobody": a user without any rights.
USER 65534:65534
WORKDIR /tmp
