#!/usr/bin/env python3
"""
Script pour uploader le CV PDF dans PostgreSQL.
Usage:
  python scripts/upload_cv_pdf.py --database-url="postgresql://user:pwd@host:port/db" [--pdf-path="path/to/cv.pdf"]
  docker exec -it portfolio_rag_backend python /app/scripts/upload_cv_pdf.py \
  --database-url="postgresql://USER:PWD@postgres:5432/DB" \
  --pdf-path="/app/documents/resume.pdf"
"""

import argparse
import os
import sys
import psycopg2
from psycopg2 import sql

def create_table(conn):
    """Crée la table cv_files si elle n'existe pas."""
    create_sql = """
    CREATE TABLE IF NOT EXISTS cv_files (
        id SERIAL PRIMARY KEY,
        filename VARCHAR(255) NOT NULL,
        content_type VARCHAR(100) NOT NULL,
        file_data BYTEA NOT NULL,
        uploaded_at TIMESTAMP DEFAULT NOW()
    );
    """
    with conn.cursor() as cur:
        cur.execute(create_sql)
    conn.commit()
    print("✅ Table cv_files créée/vérifiée")


def check_existing(conn):
    """Retourne True si un CV existe déjà."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM cv_files")
        count = cur.fetchone()[0]
    return count > 0


def delete_existing(conn):
    """Supprime tous les CV existants."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM cv_files")
    conn.commit()
    print("🗑️  CV existants supprimés")


def upload_pdf(conn, pdf_path):
    """Upload le PDF en base."""
    if not os.path.exists(pdf_path):
        print(f"❌ Fichier introuvable : {pdf_path}")
        sys.exit(1)

    filename = os.path.basename(pdf_path)
    
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    
    insert_sql = """
    INSERT INTO cv_files (filename, content_type, file_data)
    VALUES (%s, %s, %s)
    """
    
    with conn.cursor() as cur:
        cur.execute(insert_sql, (filename, 'application/pdf', pdf_bytes))
    
    conn.commit()
    print(f"✅ CV uploadé : {filename} ({len(pdf_bytes)} bytes)")


def main():
    parser = argparse.ArgumentParser(description="Upload CV PDF dans PostgreSQL")
    parser.add_argument(
        '--database-url',
        required=True,
        help='URL de connexion PostgreSQL (ex: postgresql://user:pwd@host:port/db)'
    )
    parser.add_argument(
        '--pdf-path',
        default='documents/resume.pdf',
        help='Chemin vers le fichier PDF (défaut: documents/resume.pdf)'
    )
    
    args = parser.parse_args()
    
    try:
        print(f"🔌 Connexion à la base...")
        conn = psycopg2.connect(args.database_url)
        
        create_table(conn)
        
        if check_existing(conn):
            response = input("⚠️  Un CV existe déjà. Écraser ? (y/N) : ")
            if response.lower() != 'y':
                print("❌ Annulé")
                conn.close()
                sys.exit(0)
            delete_existing(conn)
        
        upload_pdf(conn, args.pdf_path)
        
        conn.close()
        print("✅ Terminé !")
        
    except psycopg2.Error as e:
        print(f"❌ Erreur PostgreSQL : {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur : {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()