useful urls

- [interface](http://aiden.dev.localhost/)
- [pgweb on django db](http://pgweb.dev.localhost/)
- [qdrant vectore store](http://qdrant.dev.localhost/dashboard)
- [scraper api documentation](http://recommender.dev.localhost/docs)
- [traefik load balancer](http://localhost:8080/dashboard)

## Diagram of the overall architecture

```mermaid
graph TD
    subgraph "Docker Containers"
        AidenApp["aiden-web<br>Django Server"]
        MediaServer["media_server<br>nginx"]
        DB["db<br>PostgreSQL"]
        Traefik["traefik<br>Reverse Proxy"]
        Pgweb["pgweb<br>PostgreSQL Web Interface"]
        Qdrant["qdrant<br>Vector Store"]
        Recommender["aiden-recommender<br>FastApi Server"]
        Redis["redis<br>In-Memory Store"]
    end

    subgraph "Data Storage"
        PostgresData["postgres_data"]
        QdrantData["qdrant_data"]
        RedisData["redis_data"]
    end

    subgraph "Networks"
        AidenNetwork["aiden_network"]
    end

    A[User] -->|HTTP Requests| AidenApp

    AidenApp -->|CRUD Operations| DB
    AidenApp -->|Fetch Job Offers| Recommender
    AidenApp -->|Store/Fetch User Vectors| Qdrant

    Recommender -->|Store/Fetch Job Offer Vectors| Qdrant
    Recommender -->|In-Memory Queue| Redis

    DB -->|Persistent Storage| PostgresData
    Qdrant -->|Persistent Storage| QdrantData
    Redis -->|Persistent Storage| RedisData
    MediaServer -->|Serve Media Files| A[User]
```
