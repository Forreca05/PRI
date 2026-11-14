#!/bin/bash
# Starts a fresh Solr container, loads the schema and indexes the F1 collection
# (plus a schemaless copy used as a baseline in the evaluation).
# Run from anywhere: ./solr/startup.sh   (any previous meic_solr container is replaced)
set -e

cd "$(dirname "$0")"
CONTAINER=meic_solr
CORE=f1
SOLR=http://localhost:8983/solr/$CORE
DOCUMENTS=../data/processed/documents.json

# 1. Fresh container with an empty core (schema changes do not apply to indexed documents)
docker rm -f $CONTAINER > /dev/null 2>&1 || true
docker run -p 8983:8983 --name $CONTAINER -v "${PWD}:/data" -d solr:10 solr-precreate $CORE > /dev/null

echo "Waiting for Solr..."
until curl -sf "$SOLR/admin/ping" > /dev/null; do sleep 1; done

# 2. Field types and fields, through the Schema API
curl -sf -X POST -H 'Content-Type: application/json' \
    --data-binary @schema.json "$SOLR/schema" > /dev/null
echo "Schema loaded"

# 3. Index the collection (documents have an id, so re-indexing replaces instead of duplicating)
curl -sf -X POST -H 'Content-Type: application/json' \
    --data-binary @$DOCUMENTS "$SOLR/update?commit=true" > /dev/null
echo "Indexed $(curl -s "$SOLR/select?q=*:*&rows=0" | grep -o '"numFound":[0-9]*' | cut -d: -f2) documents"

# 4. Schemaless baseline: a second core with Solr's default configset and no schema of ours,
#    so Solr guesses every field type from the first values it sees
docker exec $CONTAINER solr create -c ${CORE}_schemaless > /dev/null 2>&1
curl -sf -X POST -H 'Content-Type: application/json' \
    --data-binary @$DOCUMENTS "http://localhost:8983/solr/${CORE}_schemaless/update?commit=true" > /dev/null
echo "Indexed $(curl -s "http://localhost:8983/solr/${CORE}_schemaless/select?q=*:*&rows=0" | grep -o '"numFound":[0-9]*' | cut -d: -f2) documents in ${CORE}_schemaless"
