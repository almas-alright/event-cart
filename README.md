# EventCart

EventCart is a GitHub showcase backend for learning event-driven architecture through an order workflow.

## Local Docker Foundation

The current foundation stack starts the API, PostgreSQL, and Redis:

```bash
docker compose up --build api postgres redis
```

The API health endpoint is available at:

```txt
GET http://localhost:8000/health
```

The final README will be expanded in the documentation phase.

