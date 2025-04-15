# Robotic Total Station API

This is the backend component of the RTS Network project. It is a RESTful API that provides an easy way to interact with multiple robotic total station connected to several devices running RTS workers. The API is built using the FastAPI framework and is designed to be used in conjunction with the RTS Network frontend.

## Features

This API manages connected logging devices and robotic total stations. It provides the following features:

- Automatic registration of logging devices that connect to the API (see RTS Worker project)
- Registering and managing RTS and their connection and tracking settings
- Managing RTS jobs: creating, updating, and deleting jobs like tracking a prism
- Managing RTS measurements: creating, updating, and deleting measurements
- Alignment and intrinsic calibration of RTS

## Documentation

The API documentation is available at the `/docs` endpoint. It provides detailed information about the available endpoints, request and response formats.

## Installation

Installation is done using Docker. Make sure you have Docker installed on your system.

1. Clone the repository

```bash
git clone https://github.com/Engineering-Geodesy-Bonn/rts-network
```

2. Change into the project directory

```bash
cd rts-api
```

3. Build and run the Docker container

```bash
docker-compose up -d
```

The API should now be running on `http://localhost:8000`.

### Alternative Installation

If you don't want to use Docker, you can install the API manually. Make sure you have Python 3.13 installed on your system.

1. Clone the repository

```bash
git clone https://github.com/Engineering-Geodesy-Bonn/rts-network
```

2. Change into the project directory

```bash
cd rts-api
```

3. Install the dependencies

```bash
pip install .
```

4. Run the API

```bash
python3 ./main.py
```