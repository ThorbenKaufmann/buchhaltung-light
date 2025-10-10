#!/bin/bash
pg_dump -h datacenter.itc-embedded.de -U postgres --schema-only --no-owner --no-privileges --file schema_backup.sql bhl

