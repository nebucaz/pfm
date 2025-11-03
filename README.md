#

### 2. Docker-Compose für GraphDB
```bash
# Docker Compose Datei erstellen
cat > docker-compose.yml << 'EOF'
services:
  graphdb:
    image: ontotext/graphdb:10.8.9
    container_name: graphdb
    ports:
      - 7200:7200
    environment:
      - GDB_HEAP_SIZE=2G
      - GDB_MIN_MEMORY=1G
      - GDB_MAX_MEMORY=4G
    volumes:
      - graphdb-data:/opt/graphdb/home/data
    restart: unless-stopped

volumes:
  graphdb-data:
EOF

# GraphDB starten
docker-compose up -d
```

### 3. GraphDB Repository einrichten
1. Browser öffnen: `http://localhost:7200`
2. **Repository erstellen:**
   - Klicke auf "Explore/Graphs Overview"
   - "Create new repository"
   - Repository ID: `spendcast` (oder beliebiger Name)
   - Repository title: `SpendCast Financial Data`
   - "Create" klicken

3. **Daten importieren:**
   - Repository öffnen
   - "Import" → "RDF" → "Upload files"
   - Datei `data/jeanine.ttl` auswählen
   - Target Graph: `default` (leer lassen)
   - "Import" klicken
