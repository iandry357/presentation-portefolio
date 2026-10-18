@echo off
REM test_acces.bat — tests d'acces du worker top-offres, depuis le conteneur
REM Usage : scripts\test_acces.bat (de n'importe ou). Le .env et la cle gcp_sa_top_offres.json doivent exister.
cd /d "%~dp0..\pipeline"

echo === Build ===
docker-compose build
if errorlevel 1 exit /b 1

echo.
echo === T1 BigQuery : lecture emploi_marche.stg_offres ===
docker-compose run --rm pipeline -c "from google.cloud import bigquery; from pipeline import config as c; cl=bigquery.Client(project=c.GCP_PROJECT_ID, location=c.BQ_LOCATION); r=list(cl.query('select count(*) as n from `'+c.GCP_PROJECT_ID+'.'+c.BQ_DATASET_SOURCE+'.stg_offres`').result()); print('OK stg_offres lignes =', r[0].n)"

echo.
echo === T2 BigQuery : acces au dataset top_offres (table runs) ===
docker-compose run --rm pipeline -c "from google.cloud import bigquery; from pipeline import config as c; cl=bigquery.Client(project=c.GCP_PROJECT_ID, location=c.BQ_LOCATION); r=list(cl.query('select count(*) as n from `'+c.GCP_PROJECT_ID+'.'+c.BQ_DATASET+'.runs`').result()); print('OK top_offres.runs lignes =', r[0].n)"

echo.
echo === T3 PostgreSQL : lecture de experiences ===
docker-compose run --rm pipeline -c "import psycopg2; from pipeline import config as c; cn=psycopg2.connect(host=c.PG_HOST, port=c.PG_PORT, dbname=c.PG_DB, user=c.PG_USER, password=c.PG_PASSWORD, sslmode='require'); cu=cn.cursor(); cu.execute('select count(*) from experiences'); print('OK experiences lignes =', cu.fetchone()[0])"

echo.
echo === T4 Ollama : liste des modeles ===
docker-compose run --rm pipeline -c "from agents import llm_client; print('OK modeles :', llm_client.lister_modeles())"

echo.
echo === T5 Ollama : sortie JSON contrainte (MODELE_SCORING, sinon premier modele) ===
docker-compose run --rm pipeline -c "from agents import llm_client; from pipeline import config as c; m=c.MODELE_SCORING or llm_client.lister_modeles()[0]; print('modele :', m); print('OK', llm_client.generer_json(m, 'Reponds uniquement en JSON.', 'Donne ok a true.', {'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok']}, thinking=False))"

echo.
echo === T6 OVH : reveil + embedding de 2 titres ===
docker-compose run --rm pipeline -c "from pipeline.transformation import similarite as s; s.reveiller_service(); v=s.embedder(['data scientist','ingenieur machine learning']); print('OK embeddings', v.shape)"

echo.
echo === Fin des tests ===
