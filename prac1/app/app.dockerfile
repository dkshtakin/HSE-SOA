FROM python:3.8-slim
ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
COPY person.proto .
RUN python -m pip install --no-cache-dir grpcio-tools
RUN python -m grpc_tools.protoc -I=. --python_out=. person.proto
COPY app.py .

CMD ["python", "-m", "app"]
