FROM python:3.12

WORKDIR /controller
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src .
CMD ["python3", "main.py"]