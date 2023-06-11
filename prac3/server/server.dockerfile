FROM python:3.8
ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
COPY proto/mafia.proto .
RUN python -m pip install --no-cache-dir grpcio-tools
RUN python -m grpc_tools.protoc -I=. --python_out=. --grpc_python_out=. mafia.proto
COPY server/server.py .

CMD ["bash", "-c", "while ! curl -s rabbitmq:15672 > /dev/null; do echo waiting for rabbitmq; sleep 2; done; python -u server.py"]
