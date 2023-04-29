FROM python:3.8-slim
ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /demo
COPY demo.py .

CMD ["python", "-u", "demo.py"]
