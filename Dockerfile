FROM tiangolo/uwsgi-nginx:python3.11

# Metadata
LABEL Name="SynAnno" \
      Version="1.0.0"

# Set the working directory
WORKDIR /app

# Upgrade pip
RUN python -m pip install --no-cache-dir --upgrade pip

# Install system dependencies for PyQt5
RUN apt-get update && apt-get install -y \
    qtbase5-dev \
    qtchooser \
    qt5-qmake \
    qttools5-dev-tools \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install latest Rust version via Rustup
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Verify Cargo version (should be latest)
RUN cargo --version

# Copy application code, configuration, and setup files
COPY setup.py /app/
COPY synanno /app/synanno
COPY run_production.py /app/
COPY h01/h01_104_materialization.csv /app/h01/h01_104_materialization.csv


RUN python -m pip install uv
# Install torch separately before installing the package
RUN uv pip install --system --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install missing package
RUN uv pip install --system --no-cache-dir torchsummary

# Install remaining dependencies
RUN uv pip install --system --no-cache-dir -e .
RUN uv pip install --system --no-cache-dir tqdm

# Expose the Nginx port
EXPOSE 80

# Expose Neuroglancer Port
EXPOSE 9015

# Copy uWSGI configuration
COPY uwsgi.ini /app

# Start the application
CMD ["/bin/bash", "-c", "uwsgi --ini /app/uwsgi.ini & service nginx start"]
