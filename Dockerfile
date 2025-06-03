# Use an official Python image as the base.
# Choose the Python version you're using (e.g., 3.9, 3.10, 3.11).
# "Slim" versions are smaller in size.
FROM python:3.10-slim

#  Set the working directory inside the container.
WORKDIR /app

# 3. Copy the dependencies file into the working directory.
COPY requirements.txt .

# install dependencies.
# --no-cache-dir reduces the image size by not saving the pip cache.
# --trusted-host pypi.python.org might be necessary in some networks.
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy your entire application code into the working directory.
# If you only have a main.py file, you can specify COPY main.py .
COPY . .

# 6. Expose the port your FastAPI application (Uvicorn) will run on.
# This is the same port that will be used in the CMD command.
EXPOSE 8000

# 7. Command to run your FastAPI application when the container starts.
# Uvicorn will listen on 0.0.0.0 to be accessible from outside the container.
# main:app means Uvicorn should run the object named 'app' from the file 'main.py'.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]