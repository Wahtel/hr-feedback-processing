# Use an official Python 3.10 image
FROM --platform=linux/amd64 python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy only necessary files for installing dependencies
COPY pyproject.toml poetry.lock* /app/

# Install poetry in the container
RUN pip install --no-cache-dir poetry

# Configure Poetry:
# - Do not create a virtual environment inside the container
# - Do not ask any interactive question
ENV POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

# Install project dependencies from the pyproject.toml file
RUN poetry install --no-dev  # Omit dev dependencies

# Copy the rest of your application code
COPY . /app

# Make port 3000 available to the world outside this container
EXPOSE 3000

# Set the environment variables
ENV SLACK_BOT_TOKEN=your-bot-token \
    SLACK_SIGNING_SECRET=your-signing-secret

# Command to run the application
CMD ["python", "app.py"]
