# /home/uri-home-x1/PycharmProjects/OMCB/back/Dockerfile

# 1. Use an official Python runtime as a parent image
FROM python:3.11-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the rest of your application code into the container
COPY . .

# 5. Expose the port the app runs on
EXPOSE 8000

# 6. Define the command to run your app using Gunicorn, a production-ready server
#    -w 4: Use 4 worker processes
#    -k uvicorn.workers.UvicornWorker: Use Uvicorn to run the async code
#    --bind 0.0.0.0:8000: Listen on all network interfaces on port 8000
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "main:app"]
