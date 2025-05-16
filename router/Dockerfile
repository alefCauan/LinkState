FROM python:3.9-slim

# Install system dependencies (e.g., iproute2 for ip command and procps for sysctl)
RUN apt-get update && apt-get install -y \
  iproute2 \
  iputils-ping \
  net-tools \
  nano \
  tcpdump \
  traceroute \
  && rm -rf /var/lib/apt/lists/*

# Set IP forwarding (configuration, applied at runtime via sysctls)
RUN echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
RUN echo "net.ipv4.conf.all.accept_redirects=0" >> /etc/sysctl.conf
RUN echo "net.ipv4.conf.all.send_redirects=0" >> /etc/sysctl.conf

# Set working directory
WORKDIR /app

# Copy requirements (if any)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the script
# COPY router.py .

# Run the script
CMD ["python", "router.py"]