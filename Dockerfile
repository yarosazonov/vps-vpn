# Start with the linuxserver/wireguard image
FROM linuxserver/wireguard

# Switch to root for installing packages
USER root

# Install Python and required packages using Alpine's package manager
RUN apk update && apk add --no-cache \
    python3 \
    py3-pip \
    python3-dev \
    dcron \
    curl \
    gcc \
    musl-dev

# Set working directory
WORKDIR /app

# Create and activate virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install in the virtual environment
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy monitoring application code
COPY vpn-monitor/ .

# Create directory for logs
RUN mkdir -p /data

# Create service scripts for s6-overlay (the init system linuxserver uses)
RUN mkdir -p /etc/services.d/vpnmonitor /etc/services.d/vpnmon-scheduler

## Create the monitor service script (Flask disabled)
RUN echo '#!/usr/bin/with-contenv sh' > /etc/services.d/vpnmonitor/run \
    && echo 'echo "Starting VPN Monitor services..."' >> /etc/services.d/vpnmonitor/run \
    && echo 'cd /app && /opt/venv/bin/python3 cli/monitor.py setup' >> /etc/services.d/vpnmonitor/run \
    && echo '# Flask web interface disabled' >> /etc/services.d/vpnmonitor/run \
    && echo 'exec tail -f /dev/null' >> /etc/services.d/vpnmonitor/run \
    && chmod +x /etc/services.d/vpnmonitor/run


# Create the scheduler service script
RUN mkdir -p /etc/services.d/vpnmon-scheduler && \
    echo '#!/usr/bin/with-contenv sh' > /etc/services.d/vpnmon-scheduler/run && \
    echo 'echo "Starting VPN monitoring scheduler..."' >> /etc/services.d/vpnmon-scheduler/run && \
    echo 'cd /app && exec /opt/venv/bin/python3 vpnmon/vpnmon_scheduler.py' >> /etc/services.d/vpnmon-scheduler/run && \
    chmod +x /etc/services.d/vpnmon-scheduler/run