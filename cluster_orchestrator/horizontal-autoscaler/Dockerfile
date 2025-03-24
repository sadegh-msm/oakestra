FROM python:3.12-slim-buster

# Installing git to be able to install oakestra libraries. 
RUN apt-get update && apt-get install -y --no-install-recommends git
RUN mkdir /app
COPY requirements.txt /app
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

ENV FLASK_ENV=development
# TRUE for verbose logging
ENV FLASK_DEBUG=FALSE
ENV C_FORCE_ROOT=TRUE

ENV SYSTEM_MANAGER_URL=46.249.99.42
ENV SYSTEM_MANAGER_PORT=10000

ENV MY_PORT=10180
EXPOSE 10180

ENV CLUSTER_MANAGER_URL=46.249.99.42
ENV CLUSTER_MANAGER_PORT=10100
ENV MONGO_CLUSTER_URI=mongodb://46.249.99.42:10107/
ENV DATABASE_CLUSTER_NAME=jobs
ENV COLLECTION_CLUSTER_NAME=jobs
ENV CHECK_INTERVAL=15
ENV MONGO_ROOT_URI=mongodb://46.249.99.42:10007/
ENV DATABASE_ROOT_NAME=clusters
ENV COLLECTION_ROOT_NAME=clusters
ENV COOLDOWN_SECONDS=60
ENV DATABASE_CLUSTER_HCA=horizontal_autoscaler
ENV COLLECTION_CLUSTER_HCA=scaling_data

CMD python horizontal_autoscaler.py