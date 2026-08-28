# NexusEnroll Backend

This directory contains the runnable Python backend for NexusEnroll. It implements the system as a set of FastAPI microservices with an API Gateway and in-memory repositories. 

## 1. Prerequisites

The recommended way to run the complete system is Docker Compose.

### Linux

Required:

- Docker Engine
- Docker Compose v2 (`docker compose` command)

Verify the installation with:

```bash
docker --version
docker compose version
```

On Ubuntu 24.04-based distributions, the Ubuntu repository provides the Compose v2 package as `docker-compose-v2`; Docker's own repository uses the package name `docker-compose-plugin`. Use whichever package source is appropriate for your Docker installation. Compose v2 is the supported approach for Linux; the standalone `docker-compose` command is the legacy Compose implementation.

If Docker requires root privileges, prefix Docker commands with `sudo`.

### Optional: running Python directly

Python 3.12 is recommended to match the container image.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
To set up a python virtual environment and install all requirements to run directly and for pytest.

## 2. Run the complete system with Docker Compose

From this directory:

```bash
docker compose up --build
```

To stop the system:
Ctrl + C on terminal

## 3. Service endpoints

The following host ports are configured by `docker-compose.yml`:

| Component | Host port | Swagger UI | Purpose |
|---|---:|---|---|
| API Gateway | 8000 | http://localhost:8000/docs | Public client-facing API entry point |
| Identity Service | 8001 | http://localhost:8001/docs | Student, faculty and administrator accounts |
| Enrollment Service | 8002 | http://localhost:8002/docs | Courses, offerings, enrolment, schedules and validation |
| Faculty Service | 8003 | http://localhost:8003/docs | Rosters, grades and course-change requests |
| Administrator Service | 8004 | http://localhost:8004/docs | Administrative management, approvals and reports |
| Notification Service | 8005 | Not host-exposed | Internal notification handling |

The API Gateway is the intended public entry point for client applications. The Identity, Enrollment, Faculty and Administrator ports are also mapped to the host deliberately so that the individual Swagger UIs can be used during development and demonstration. The Notification Service is internal-only and has no host port mapping.

## 4. Architecture and communication

The runtime structure is:

```text
Web SPA / Mobile App
        |
        v
API Gateway :8000
        |
        +----> Identity Service :8001
        +----> Enrollment Service :8002
        +----> Faculty Service :8003
        +----> Administrator Service :8004

Enrollment / Faculty Services
        |
        +----> Notification Service :8005
```

The services communicate through HTTP/REST using `httpx`. Within the Docker Compose network, services address each other by service name rather than `localhost`, for example:

```text
http://identity-service:8001
http://enrollment-service:8002
http://faculty-service:8003
http://admin-service:8004
http://notification-service:8005
```

The API Gateway forwards client requests to the appropriate service and blocks internal-only endpoints. It also does not expose the Notification Service.

## 5. Project structure

```text
source/
├── common/
│   ├── api.py
│   ├── domain/
│   │   └── models.py
│   ├── patterns/
│   │   ├── command.py
│   │   ├── factory.py
│   │   ├── observer.py
│   │   ├── state.py
│   │   └── validation.py
│   └── repositories/
│       └── memory.py
│
├── services/
│   ├── gateway/app.py
│   ├── identity/app.py
│   ├── enrollment/app.py
│   ├── faculty/app.py
│   ├── admin/app.py
│   └── notification/app.py
│
├── tests/
│   ├── test_gateway.py
│   └── test_patterns.py
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── INTEGRATION_DEMO.md
```

The `common` package contains the shared domain model, in-memory repositories, and pattern implementations. The `services` package contains the independently runnable FastAPI applications.

## 6. Design patterns in the implementation

The current implementation demonstrates five object-oriented design patterns:

- **Factory Method** – `UserFactory` creates Student, Faculty and Administrator objects through dedicated creators.
- **Chain of Responsibility** – enrolment validation is divided into prerequisite, time-conflict and capacity validators.
- **Observer** – domain events are published to observers; `HttpNotificationObserver` forwards relevant events to the Notification Service.
- **Command** – course modifications are represented by concrete command objects such as description, prerequisite and capacity changes.
- **State** – grade submissions transition through state-specific objects such as Draft, Pending, Rejected and Submitted.

Enrolment mutations also use a service-local rollback boundary so a failed operation does not leave partially updated in-memory state.

## 7. Running tests

Create and activate a virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then run:

```bash
pytest -q
```

The test suite covers the design-pattern implementations and API Gateway behaviour.

## 8. Using the Swagger interfaces

FastAPI automatically provides interactive API documentation through Swagger UI.

For development and demonstration, open:

```text
http://localhost:8000/docs   # API Gateway
http://localhost:8001/docs   # Identity
http://localhost:8002/docs   # Enrollment
http://localhost:8003/docs   # Faculty
http://localhost:8004/docs   # Administrator
```

The individual service Swagger pages are useful for demonstrating the business logic directly. The gateway remains the intended interface for an actual web or mobile client.
