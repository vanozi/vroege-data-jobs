FROM mcr.microsoft.com/playwright/python:v1.25.0-focal

# create the appropriate directories
WORKDIR /app

# set environment variables
ENV APP_HOME=/app
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install python dependencies
COPY ./requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt


COPY . .

RUN python /app/transactions.py
