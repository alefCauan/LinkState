FROM python:3.9-slim
RUN pip install netifaces
WORKDIR /app
COPY router.py .
CMD ["python", "router.py"]