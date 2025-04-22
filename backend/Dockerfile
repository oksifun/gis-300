FROM rnix/openssl-gost AS openssl-gost

FROM dockerhub.timeweb.cloud/python:3.6

COPY --from=openssl-gost /usr/local/ssl /usr/local/ssl
COPY --from=openssl-gost /usr/local/ssl/bin/openssl /usr/bin/openssl
#COPY --from=openssl-gost /usr/local/curl /usr/local/curl
#COPY --from=openssl-gost /usr/local/curl/bin/curl /usr/bin/curl
COPY --from=openssl-gost /usr/local/bin/gostsum /usr/local/bin/gostsum
COPY --from=openssl-gost /usr/local/bin/gost12sum /usr/local/bin/gost12sum

#COPY --from=openssl-gost /usr/local/ssl/lib/pkgconfig/* /usr/lib/x86_64-linux-gnu/pkgconfig/
#COPY --from=openssl-gost /usr/local/curl/lib/pkgconfig/* /usr/lib/x86_64-linux-gnu/pkgconfig/

RUN echo "/usr/local/ssl/lib" >> /etc/ld.so.conf.d/ssl.conf && ldconfig

RUN openssl version -a && openssl ciphers -s
#    && cat /usr/local/ssl/openssl.cnf

RUN apt-get update \
    && apt-get install -y locales qrencode util-linux-locales python3-uno \
    && wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y -f ./google-chrome-stable_current_amd64.deb \
    && sed -i 's/# ru_RU.UTF-8 UTF-8/ru_RU.UTF-8 UTF-8/' /etc/locale.gen \
    && /usr/sbin/locale-gen && echo 'LANG=ru_RU.UTF-8' > /etc/locale.conf \
    && echo Europe/Moscow | tee /etc/timezone && dpkg-reconfigure --frontend noninteractive tzdata \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /var/www

COPY ./backend/requirements.txt ./deploy/pygost-5.11 ./

RUN pip install -r requirements.txt && python setup.py install

ENV PYTHONPATH=/usr/lib/python3/dist-packages:/var/www SETTINGS_FILE=local.yml PROC_NUM=8 LANG=ru_RU.UTF-8 DJANGO_SETTINGS_MODULE=config.settings C_FORCE_ROOT=1

COPY backend /var/www

CMD ["python", "main.py", "--xheaders=True", "--port=8888"]