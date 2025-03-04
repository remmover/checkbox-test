
---
# Checkbox Test Service

This repository contains the source code for the Checkbox Test Service. The service runs using Docker and Docker Compose. Follow the instructions below to set up, build, and run the project.

## Prerequisites

- **Docker**: Ensure that Docker is installed on your system. You can download it from [Docker's official website](https://www.docker.com/get-started).
- **Docker Compose**: Verify that Docker Compose is installed. You can find installation instructions on the [Docker Compose documentation page](https://docs.docker.com/compose/install/).

## Setup and Installation

1. **Clone the Repository**

   Open a terminal and execute the following command to clone the repository:

   ```bash
   git clone https://github.com/remmover/checkbox-test.git
   ```

2. **Navigate to the Project Directory**

   Change into the project's root directory:

   ```bash
   cd checkbox-test
   ```

3. **Configure Environment Variables**

   The project requires specific environment variables to run correctly.

   - **Create a `.env` File**

     Duplicate the provided `.env_example` file and rename it to `.env`:

     ```bash
     cp .env_example .env
     ```

   - **Edit the `.env` File**

     Open the `.env` file in a text editor and set the necessary environment variables.

## Building and Running the Service

Build and run the service with a single command:

```bash
docker-compose up --build
```

This command builds the Docker containers and starts the service, making it accessible according to the configurations specified in your `.env` file.

## Running Tests

Tests can be executed locally without using Docker, as all requests to Docker containers are mocked and replaced. To run the test suite, simply execute:

```bash
pytest
```

This command will run the tests and display the results in the terminal.

## Additional Information

Documentation for the routes and most functions is available at [https://remmover.github.io/checkbox-test/](https://remmover.github.io/checkbox-test/). For a more enhanced view of the documentation, it is recommended to navigate directly to the repository's documentation at `.docs/html/index.html`.

For more detailed information and advanced configurations, please refer to the project's documentation or inspect the source code in this repository.

--- 
