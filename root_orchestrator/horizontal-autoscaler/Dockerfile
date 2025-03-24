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

ENV MY_PORT=10080
EXPOSE 10080

ENV CHECK_INTERVAL=10
ENV CLUSTER_MANAGER_URL=46.249.99.42
ENV CLUSTER_MANAGER_PORT=10180
ENV MONGO_ROOT_URI=mongodb://46.249.99.42:10007/
ENV DATABASE_ROOT_HCA=horizontal_autoscaler
ENV COLLECTION_ROOT_HCA=service_cluster_mapping

CMD python horizontal_autoscaler.py