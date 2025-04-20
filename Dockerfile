# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dependency file
# Assumes all runtime dependencies are listed in pyproject.toml
COPY pyproject.toml ./

# Install project dependencies
# Using --no-cache-dir reduces image size
# Installing '.' installs the package defined in pyproject.toml
# We install without dev extras for a smaller production image
RUN pip install --no-cache-dir .

# Copy the application source code
COPY src/ ./src/

# Make port 8080 available (default for FastMCP)
EXPOSE 8080

# Define environment variable defaults (can be overridden at runtime)
# These are crucial for the server to function
ENV FASTMCP_HOST=0.0.0.0
ENV FASTMCP_PORT=8080
# API Keys and URL should be provided at runtime for security
# ENV SPACEBRIDGE_API_URL=
# ENV SPACEBRIDGE_API_KEY=
# ENV OPENAI_API_KEY=

# Run the application using the entry point defined in pyproject.toml
CMD ["spacebridge-mcp-server"]
