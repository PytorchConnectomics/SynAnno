# Stage 1: Builder Stage
FROM tiangolo/uwsgi-nginx-flask:python3.9

# Metadata
LABEL Name="SynAnno" \
      Version="1.0.0"

# Upgrade pip
RUN python -m pip install --upgrade pip

# Set up directories and permissions in a single RUN statement to reduce image layers
RUN mkdir -p /home/nginx/.cloudvolume/secrets \
    && chown -R nginx:nginx /home/nginx \
    && usermod -d /home/nginx -s /bin/bash nginx

RUN mkdir -p /tmp/flask_session && chown -R nginx:nginx /tmp/flask_session

# Set the working directory to /app
WORKDIR /app

ENV DEBUG_APP=False
ENV SECRET_KEY=your-secret-key
ENV APP_IP=0.0.0.0
ENV APP_PORT=80

# Copy setup.py, application code and configs
COPY setup.py /app/
COPY synanno /app/synanno
COPY run_production.py /app/
COPY h01/synapse-export_000000000000.csv /app/h01/synapse-export_000000000000.csv

# Create required directories
RUN mkdir -p files/

# Set ownership and write permissions of the static files
RUN chown -R nginx:nginx /app/synanno/static/Images
RUN chmod -R u+w /app/synanno/static/Images

# Install dependencies using setup.py
RUN pip install --no-cache-dir -e .

# Expose the Nginx port (port 80)
EXPOSE 80

# Copy uwsgi.ini and nginx.conf files
COPY uwsgi.ini /app
COPY nginx.conf /etc/nginx/nginx.conf

# Run Nginx and uWSGI in the foreground
CMD ["/bin/bash", "-c", "uwsgi --ini /app/uwsgi.ini & service nginx start"]
