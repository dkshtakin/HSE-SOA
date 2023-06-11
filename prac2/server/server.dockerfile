FROM python:3.8-slim
ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
COPY proto/mafia.proto .
RUN python -m pip install --no-cache-dir grpcio-tools
RUN python -m grpc_tools.protoc -I=. --python_out=. --grpc_python_out=. mafia.proto
COPY server/server.py .

CMD ["python", "-u", "-m", "server"]
