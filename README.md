# GitRepoAPI

API FastAPI permettant d'exposer les repositories GitHub les plus populaires depuis PostgreSQL.

## Configuration

Copier le fichier d'exemple et renseigner les identifiants de la base de données :

```bash
cp .env.example .env
```

Variables attendues :

```env
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=github_data
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
API_PORT=8000
```

## Démarrage

```bash
docker compose up --build
```

L'API est disponible sur :

```text
http://localhost:8000
```

## Endpoint

L'API expose le résultat de la requête suivante :

```sql
SELECT * FROM github.repositories
ORDER BY stars DESC, updated_at DESC
LIMIT 100;
```

via l'endpoint :

```http
GET /repositories
GET /repositories/top
```

Exemple :

```bash
curl "http://localhost:8000/repositories?limit=100"
```

Le service renvoie un JSON contenant les champs de `github.repositories` triés par `stars` puis `updated_at`.
