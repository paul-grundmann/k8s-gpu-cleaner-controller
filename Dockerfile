FROM python:3.13
WORKDIR /controller
COPY pyproject.toml .
RUN pip install uv
RUN uv sync
COPY src .
CMD ["uv","run", "main.py"]