FROM python:3.12
WORKDIR /controller
COPY pyproject.toml .
RUN pip install uv pip-system-certs --use-feature=truststore

RUN uv sync
COPY src .
CMD ["uv","run", "main.py"]