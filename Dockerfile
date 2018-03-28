FROM python:3.6

MAINTAINER Ronan Delacroix <ronan.delacroix@gmail.com>

COPY ./requirements.txt /opt/app/
WORKDIR /opt/app

RUN pip3 install --no-cache-dir -r requirements.txt

RUN mkdir /opt/current_folder
VOLUME /opt/current_folder

ENV PYTHONPATH=$PYTHONPATH:/opt/app:/opt/current_folder

COPY . /opt/app

ENTRYPOINT ["python3", "/opt/app/bin/jobmanager-client"]
