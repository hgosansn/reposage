FROM python:3-slim AS builder
ADD . /app
WORKDIR /app

# We are installing a dependency here directly into our app source dir
RUN python -m pip install --upgrade pip
RUN pip install -r ./requirements.txt


# Set environment variables from the github action to the container
ARG GITHUB_TOKEN
ARG GITHUB_REPOSITORY

ENV GITHUB_TOKEN=$GITHUB_TOKEN
ENV GITHUB_REPOSITORY=$GITHUB_REPOSITORY

# A distroless container image with Python and some basics like SSL certificates
# https://github.com/GoogleContainerTools/distroless
FROM gcr.io/distroless/python3-debian10
COPY --from=builder /app /app
WORKDIR /app
ENV PYTHONPATH /app
CMD ["/bot.py"]