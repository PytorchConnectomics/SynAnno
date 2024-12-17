FROM tiangolo/uwsgi-nginx-flask:python3.10

# Metadata
LABEL Name="SynAnno" \
      Version="1.0.0"

# Environment variables
ENV DEBUG_APP=False
ENV SECRET_KEY=your-secret-key
ENV APP_IP=0.0.0.0
ENV APP_PORT=80
ENV STATIC_PATH /app/synanno/static

# Set the working directory
WORKDIR /app

# Upgrade pip
RUN python -m pip install --no-cache-dir --upgrade pip

# Create necessary directories and set ownership/permissions
RUN mkdir -p /tmp/flask_session /app/files /app/synanno/static/Images \
    && chown -R nginx:nginx /tmp /app/files /app/synanno/static/Images \
    && chmod -R u+w /app/synanno/static/Images

# Copy application code, configuration, and setup files
COPY setup.py /app/
COPY synanno /app/synanno
COPY run_production.py /app/
COPY h01/synapse-export_000000000000.csv /app/h01/synapse-export_000000000000.csv

# Install application and dependencies from setup.py
RUN pip install --no-cache-dir -e .

# Expose the Nginx port
EXPOSE 80

# Copy uWSGI configuration
COPY uwsgi.ini /app

# Start the application
CMD ["/bin/bash", "-c", "uwsgi --ini /app/uwsgi.ini & service nginx start"]
