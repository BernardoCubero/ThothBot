FROM rasa/rasa:3.6.20-full

WORKDIR /app

COPY . /app

USER root

RUN pip install --no-cache-dir -r requirements.txt

USER 1001

EXPOSE 5005

CMD ["run", "--enable-api", "--cors", "*", "--debug"]
