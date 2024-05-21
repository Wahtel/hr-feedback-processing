# Use an official Python 3.10 image
FROM --platform=linux/amd64 python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy only necessary files for installing dependencies
COPY Pipfile Pipfile.lock /app/

# Install pipenv in the container
RUN pip install --no-cache-dir pipenv

# Install project dependencies from the Pipfile.lock
RUN pipenv install --deploy --ignore-pipfile

# Copy the rest of your application code
COPY . /app

# Make port 3000 available to the world outside this container
EXPOSE 3000

# Set the environment variables
ENV SLACK_BOT_TOKEN=your-bot-token \
    SLACK_SIGNING_SECRET=your-signing-secret

# Command to run the application
CMD ["pipenv", "run", "python", "app.py"]