// Jenkins-Pipeline für buchhaltung-light (BHL)
//
// Testet das System gegen eine dedizierte PostgreSQL-TEST-Datenbank:
//   1. Schreibt eine Test-config/db.yaml (überschreibt die im Repo committete!)
//   2. Legt Python-venv an und installiert Abhängigkeiten
//   3. Initialisiert die Test-DB frisch (Schema + SKR03-Seed)
//   4. Smoke-Test: kompiliert alle Python-Skripte
//   5. pytest gegen die Test-DB
//
// Voraussetzungen auf dem Jenkins-Agent:
//   - python3 (inkl. venv) und psql im PATH
//   - Netzzugriff auf den PostgreSQL-Testserver
//   - Jenkins-Credential (Secret Text) mit ID 'bhl-test-db-password'
//
// SICHERHEIT: Die Pipeline weigert sich, gegen DB-Namen 'bhl' oder 'bhl-ug'
// (Produktion) zu laufen. Niemals diese Werte als DB_NAME setzen.

pipeline {
  agent any

  environment {
    DB_HOST = 'datacenter.itc-embedded.de'
    DB_PORT = '5432'
    DB_USER = 'postgres'
    DB_NAME = 'bhl_ci_test'        // dedizierte Test-DB – NICHT 'bhl' / 'bhl-ug'
    DB_PASS = credentials('bhl-test-db-password')
  }

  options {
    timestamps()
    timeout(time: 20, unit: 'MINUTES')
  }

  stages {
    stage('Guard: keine Produktiv-DB') {
      steps {
        sh '''
          set -eu
          case "$DB_NAME" in
            bhl|bhl-ug)
              echo "ABBRUCH: DB_NAME='$DB_NAME' ist die Produktiv-DB." >&2
              exit 1 ;;
          esac
          echo "OK – Ziel-DB: $DB_NAME auf $DB_HOST"
        '''
      }
    }

    stage('Test-Konfiguration schreiben') {
      steps {
        // Überschreibt die im Repo committete config/db.yaml mit Test-Werten.
        // $DB_PASS wird in der Shell expandiert (nicht in Groovy), damit Jenkins
        // das Secret in den Logs maskiert.
        sh '''
          set -eu
          cat > config/db.yaml <<EOF
dbname: $DB_NAME
user: $DB_USER
password: $DB_PASS
host: $DB_HOST
port: $DB_PORT
EOF
          echo "config/db.yaml geschrieben (dbname=$DB_NAME)."
        '''
      }
    }

    stage('Python-Umgebung') {
      steps {
        sh '''
          set -eu
          python3 -m venv venv
          . venv/bin/activate
          pip install --upgrade pip
          pip install -r requirements.txt -r requirements-dev.txt
        '''
      }
    }

    stage('Test-DB initialisieren') {
      steps {
        // setup_db.py fragt bei --drop-existing interaktiv nach Bestätigung "ja".
        // In der CI füttern wir die Bestätigung über stdin.
        sh '''
          set -eu
          . venv/bin/activate
          printf 'ja\\n' | python3 python/setup_db.py --drop-existing
        '''
      }
    }

    stage('Smoke: Skripte kompilieren') {
      steps {
        sh '''
          set -eu
          . venv/bin/activate
          python3 -m compileall -q python
        '''
      }
    }

    stage('pytest') {
      steps {
        sh '''
          set -eu
          . venv/bin/activate
          pytest --junitxml=test-results/junit.xml \
                 --cov=python --cov-report=xml:test-results/coverage.xml
        '''
      }
    }
  }

  post {
    always {
      junit testResults: 'test-results/junit.xml', allowEmptyResults: true
      // config/db.yaml mit Secret nicht im Workspace zurücklassen
      sh 'rm -f config/db.yaml || true'
    }
  }
}
