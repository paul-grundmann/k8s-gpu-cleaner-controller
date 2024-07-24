FROM python:3.12

WORKDIR /controller
COPY requirements.txt .
COPY src .
RUN pip install -r requirements.txt
CMD ["python3", "src/main.py"]