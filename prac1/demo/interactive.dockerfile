FROM python:3.8-slim
ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /interactive
COPY interactive.py .

CMD ["python", "-u", "interactive.py"]
