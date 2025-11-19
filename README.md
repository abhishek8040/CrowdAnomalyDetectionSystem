## Running the Project with Docker

This project provides Dockerfiles for both the backend (Python) and frontend (JavaScript/Vite) applications, along with a `docker-compose.yaml` for orchestrating the services.

### Requirements
- **Backend:** Python 3.13 (as specified in `Dockerfile.backend`)
- **Frontend:** Node.js 22.13.1 (as specified in `Dockerfile.frontend`)

### Environment Variables
- Both backend and frontend support environment variables via `.env` files (`./backend/.env`, `./frontend/.env`).
- If you need to set custom environment variables, create or edit these files before building. Uncomment the `env_file` lines in `docker-compose.yaml` if you want Docker Compose to load them automatically.

### Build and Run Instructions
1. Ensure Docker and Docker Compose are installed.
2. From the project root, run:
   ```sh
   docker compose up --build
   ```
   This will build and start both services.

### Ports
- **Frontend:**
  - Exposes `4173` (Vite preview) and `3000` (optional/dev server)
  - Accessible at `http://localhost:4173` or `http://localhost:3000`
- **Backend:**
  - No port is exposed by default. If your backend serves on a specific port, uncomment and adjust the `ports` section in `docker-compose.yaml`.

### Special Configuration
- Both services run as non-root users for improved security.
- The backend uses a Python virtual environment for dependencies.
- The frontend build removes `.env` files from the image for safety.
- Both services are connected via the `appnet` Docker network.

### Notes
- If you need to expose the backend API, edit `docker-compose.yaml` and add the appropriate port mapping under `python-backend`.
- For development, you may want to mount source code as volumes or adjust the Dockerfiles for hot-reloading.

Refer to `GETTING_STARTED.md` for more detailed setup and usage instructions.
