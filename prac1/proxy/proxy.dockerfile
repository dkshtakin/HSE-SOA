FROM python:3.8-slim
ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /proxy
COPY proxy.py .

CMD ["python", "-m", "proxy"]
