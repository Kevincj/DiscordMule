FROM python:3.10.1

RUN apt update && apt upgrade -y && \
    apt install espeak -y

COPY ./discord_mule/req.txt . 

RUN pip install --upgrade pip
RUN pip install -r ./req.txt
RUN pip install discord.py[voice]

COPY . /discord_mule

WORKDIR /discord_mule

CMD ["python3.10", "bot.py"]
