FROM rasa/rasa-sdk:3.6.2

WORKDIR /app

COPY . /app

USER root

RUN pip install --no-cache-dir -r actions/requirements-actions.txt

USER 1001