FROM tiangolo/uwsgi-nginx-flask:python3.9

LABEL Name="SynAnno" \
      Version="1.0.0"

ENV UWSGI_INI ./uwsgi.ini
RUN python -m pip install --upgrade pip

RUN mkdir -p /home/nginx/.cloudvolume/secrets && chown -R nginx /home/nginx && usermod -d /home/nginx -s /bin/bash nginx

COPY requirements.txt /app/.

RUN pip install numpy && \
    pip install -r requirements.txt
COPY . /app

EXPOSE 80

CMD ["uwsgi", "--ini", "/app/uwsgi.ini"]
