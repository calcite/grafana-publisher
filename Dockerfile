FROM python:3.7.12-slim-buster
MAINTAINER Josef Nevrly <jnevrly@alps.cz>

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE 1
# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED 1

ENV GIT_USER_NAME "Grafana publisher"
ENV GIT_USER_EMAIL "grafana@publisher.io"

# Install Poetry
RUN apt-get update && apt-get -y install curl
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -
ENV PATH="/root/.poetry/bin:${PATH}"

# Install and configure git
RUN apt-get -y install git
RUN git config --global user.name $GIT_USER_NAME
RUN git config --global user.email $GIT_USER_NAME

# Install the source
WORKDIR /usr/src/app
COPY . ./
RUN poetry config virtualenvs.create false && poetry install --no-dev --no-interaction --no-ansi

WORKDIR /app
#CMD ["grafana_publisher"]
ENTRYPOINT [""]
