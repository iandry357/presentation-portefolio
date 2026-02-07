#!/usr/bin/env python3
"""
Script pour uploader le CV PDF dans PostgreSQL + générer images PNG.
Usage:
  python scripts/upload_cv_pdf.py --database-url="postgresql://user:pwd@host:port/db" [--pdf-path="path/to/cv.pdf"]
"""

import argparse
import os
import sys
import psycopg2
from psycopg2 import sql
# from pdf2image import convert_from_path
from io import BytesIO

def create_tables(conn):
    """Crée les tables cv_files et cv_pages si elles n'existent pas."""
    create_cv_files_sql = """
    CREATE TABLE IF NOT EXISTS cv_files (
        id SERIAL PRIMARY KEY,
        filename VARCHAR(255) NOT NULL,
        content_type VARCHAR(100) NOT NULL,
        file_data BYTEA NOT NULL,
        uploaded_at TIMESTAMP DEFAULT NOW()
    );
    """
    
    create_cv_pages_sql = """
    CREATE TABLE IF NOT EXISTS cv_pages (
        id SERIAL PRIMARY KEY,
        page_number INTEGER NOT NULL,
        image_data BYTEA NOT NULL,
        width INTEGER,
        height INTEGER,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """
    
    with conn.cursor() as cur:
        cur.execute(create_cv_files_sql)
        cur.execute(create_cv_pages_sql)
    conn.commit()
    print("✅ Tables cv_files et cv_pages créées/vérifiées")


def check_existing(conn):
    """Retourne True si un CV existe déjà."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM cv_files")
        count = cur.fetchone()[0]
    return count > 0


def delete_existing(conn):
    """Supprime tous les CV et pages existants."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM cv_pages")
        cur.execute("DELETE FROM cv_files")
    conn.commit()
    print("🗑️  CV et pages existants supprimés")


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
    print(f"✅ CV PDF uploadé : {filename} ({len(pdf_bytes)} bytes)")


def convert_and_store_images(conn, pdf_path):
    """Convertit le PDF en images PNG et les stocke en base."""
    print("🔄 Conversion PDF → Images PNG (300 DPI)...")
    
    try:
        import fitz  # PyMuPDF
        from PIL import Image
        
        # Ouvrir PDF
        pdf_document = fitz.open(pdf_path)
        num_pages = len(pdf_document)
        
        print(f"📄 {num_pages} page(s) détectée(s)")
        
        for page_num in range(num_pages):
            # Render page à 300 DPI (matrix scale = 300/72 = 4.17)
            page = pdf_document[page_num]
            mat = fitz.Matrix(4.17, 4.17)  # 300 DPI
            pix = page.get_pixmap(matrix=mat)
            
            # Convertir en PNG bytes
            img_bytes = pix.tobytes("png")
            
            # Insérer en base
            insert_sql = """
            INSERT INTO cv_pages (page_number, image_data, width, height)
            VALUES (%s, %s, %s, %s)
            """
            
            with conn.cursor() as cur:
                cur.execute(insert_sql, (
                    page_num + 1,
                    img_bytes,
                    pix.width,
                    pix.height
                ))
            
            print(f"  ✅ Page {page_num + 1} : {pix.width}x{pix.height}px ({len(img_bytes) // 1024}KB)")
        
        pdf_document.close()
        conn.commit()
        print(f"✅ {num_pages} image(s) stockée(s) en base de données")
        
    except Exception as e:
        print(f"❌ Erreur conversion : {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Upload CV PDF + génération images PNG")
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
        
        create_tables(conn)
        
        if check_existing(conn):
            response = input("⚠️  Un CV existe déjà. Écraser ? (y/N) : ")
            if response.lower() != 'y':
                print("❌ Annulé")
                conn.close()
                sys.exit(0)
            delete_existing(conn)
        
        # Upload PDF
        upload_pdf(conn, args.pdf_path)
        
        # Convertir et stocker images
        convert_and_store_images(conn, args.pdf_path)
        
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