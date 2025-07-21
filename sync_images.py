#!/usr/bin/env python3
"""
Image sync script for AWS S3
Uploads new/modified images and tracks state in a local database
"""

import os
import sqlite3
import hashlib
import time
import logging
from pathlib import Path
from datetime import datetime
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

# Configuration
BUCKET_NAME = "hfxbikeparking"
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.JPG', '.JPEG'}
DB_FILE = "sync_state.db"
LOG_FILE = "sync.log"

# AWS S3 - no endpoint needed for standard AWS S3

class ImageSyncer:
    def __init__(self, photos_dir="."):
        self.photos_dir = Path(photos_dir).resolve()
        # Load environment variables from .env file
        load_dotenv()
        self.setup_logging()
        self.setup_database()
        self.setup_s3_client()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.photos_dir / LOG_FILE),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def setup_database(self):
        """Initialize SQLite database to track file states"""
        self.db_path = self.photos_dir / DB_FILE
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS file_state (
                filepath TEXT PRIMARY KEY,
                file_hash TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                last_modified REAL NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                s3_key TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def setup_s3_client(self):
        """Setup AWS S3 client using boto3"""
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
            )

            # Test connection
            self.s3_client.head_bucket(Bucket=BUCKET_NAME)
            self.logger.info(f"Successfully connected to S3 bucket: {BUCKET_NAME}")

        except NoCredentialsError:
            self.logger.error("AWS credentials not found. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables.")
            raise
        except ClientError as e:
            self.logger.error(f"Failed to connect to S3: {e}")
            raise

    def get_file_hash(self, filepath):
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def get_image_files(self):
        """Get all image files in the directory"""
        image_files = []
        for file_path in self.photos_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in IMAGE_EXTENSIONS:
                image_files.append(file_path)
        return sorted(image_files)

    def needs_upload(self, filepath):
        """Check if file needs to be uploaded (new or modified)"""
        file_stat = filepath.stat()
        current_hash = self.get_file_hash(filepath)
        cursor = self.conn.execute(
            "SELECT file_hash, file_size, last_modified FROM file_state WHERE filepath = ?",
            (str(filepath),)
        )
        result = cursor.fetchone()

        if not result:
            return True, current_hash  # New file
        stored_hash, stored_size, stored_mtime = result

        # Check if file has changed
        if (current_hash != stored_hash or 
            file_stat.st_size != stored_size or 
            file_stat.st_mtime != stored_mtime):
            return True, current_hash
        return False, current_hash

    def upload_to_s3(self, filepath, file_hash):
        # Use just the filename as the key 
        s3_key = filepath.name

        try:
            self.logger.info(f"Uploading {filepath.name} to S3...")

            # Upload file
            self.s3_client.upload_file(
                str(filepath),
                BUCKET_NAME,
                s3_key,
                ExtraArgs={
                    'ContentType': self.get_content_type(filepath.suffix.lower()),
                    'Metadata': {
                        'original-name': filepath.name,
                        'upload-date': datetime.utcnow().isoformat()
                    }
                }
            )

            file_stat = filepath.stat()
            self.conn.execute("""
                INSERT OR REPLACE INTO file_state 
                (filepath, file_hash, file_size, last_modified, s3_key)
                VALUES (?, ?, ?, ?, ?)
            """, (str(filepath), file_hash, file_stat.st_size, file_stat.st_mtime, s3_key))
            self.conn.commit()
            self.logger.info(f"Successfully uploaded {filepath.name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to upload {filepath.name}: {e}")
            return False

    def get_content_type(self, extension):
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        return content_types.get(extension.lower(), 'application/octet-stream')
    
    def sync_images(self):
        self.logger.info("Starting image sync...")
        image_files = self.get_image_files()
        self.logger.info(f"Found {len(image_files)} image files")

        uploaded_count = 0
        skipped_count = 0
        failed_count = 0

        for filepath in image_files:
            try:
                needs_upload, file_hash = self.needs_upload(filepath)
                if needs_upload:
                    if self.upload_to_s3(filepath, file_hash):
                        uploaded_count += 1
                    else:
                        failed_count += 1
                else:
                    skipped_count += 1
                    self.logger.debug(f"Skipping {filepath.name} (already uploaded)")
            except Exception as e:
                self.logger.error(f"Error processing {filepath.name}: {e}")
                failed_count += 1

        self.logger.info(f"Sync completed: {uploaded_count} uploaded, {skipped_count} skipped, {failed_count} failed")
        return uploaded_count, skipped_count, failed_count

    def cleanup_deleted_files(self):
        """Remove entries from database for files that no longer exist locally"""
        cursor = self.conn.execute("SELECT filepath FROM file_state")
        db_files = [row[0] for row in cursor.fetchall()]

        removed_count = 0
        for db_filepath in db_files:
            if not Path(db_filepath).exists():
                self.conn.execute("DELETE FROM file_state WHERE filepath = ?", (db_filepath,))
                removed_count += 1

        if removed_count > 0:
            self.conn.commit()
            self.logger.info(f"Cleaned up {removed_count} deleted files from database")
    def close(self):
        if self.conn:
            self.conn.close()

def main():
    syncer = ImageSyncer("photos")

    try:
        syncer.cleanup_deleted_files()
        # Sync images
        uploaded, skipped, failed = syncer.sync_images()
        if failed > 0:
            exit(1)
        else:
            exit(0)

    except KeyboardInterrupt:
        syncer.logger.info("Sync interrupted by user")
        exit(1)
    except Exception as e:
        syncer.logger.error(f"Sync failed: {e}")
        exit(1)
    finally:
        syncer.close()

if __name__ == "__main__":
    main()
