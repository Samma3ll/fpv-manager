"""MinIO client for file storage operations."""

import logging
from io import BytesIO
from minio import Minio
from minio.error import S3Error

from app.core.config import settings

logger = logging.getLogger(__name__)


class MinIOClient:
    """MinIO S3-compatible object storage client."""

    def __init__(self):
        """Initialize MinIO client with settings."""
        self.client = Minio(
            settings.minio_public_url.replace("http://", "").replace("https://", ""),
            access_key=settings.minio_root_user,
            secret_key=settings.minio_root_password,
            secure=False,  # http for development
        )
        self.bucket_blackbox = settings.minio_bucket_blackbox_logs
        self.bucket_assets = settings.minio_bucket_assets

    def upload_file(
        self, bucket: str, object_name: str, file_content: bytes
    ) -> str:
        """
        Upload a file to MinIO.

        Args:
            bucket: Bucket name
            object_name: Object key/path in bucket
            file_content: File content as bytes

        Returns:
            Object name (key) if successful

        Raises:
            S3Error: If upload fails
        """
        try:
            self.client.put_object(
                bucket_name=bucket,
                object_name=object_name,
                data=BytesIO(file_content),
                length=len(file_content),
            )
            logger.info(f"Uploaded {object_name} to {bucket}")
            return object_name
        except S3Error as e:
            logger.error(f"Failed to upload {object_name} to {bucket}: {e}")
            raise

    def download_file(self, bucket: str, object_name: str) -> bytes:
        """
        Download a file from MinIO.

        Args:
            bucket: Bucket name
            object_name: Object key/path in bucket

        Returns:
            File content as bytes

        Raises:
            S3Error: If download fails
        """
        try:
            response = self.client.get_object(bucket_name=bucket, object_name=object_name)
            content = response.read()
            response.close()
            logger.info(f"Downloaded {object_name} from {bucket}")
            return content
        except S3Error as e:
            logger.error(f"Failed to download {object_name} from {bucket}: {e}")
            raise

    def delete_file(self, bucket: str, object_name: str) -> None:
        """
        Delete a file from MinIO.

        Args:
            bucket: Bucket name
            object_name: Object key/path in bucket

        Raises:
            S3Error: If deletion fails
        """
        try:
            self.client.remove_object(bucket_name=bucket, object_name=object_name)
            logger.info(f"Deleted {object_name} from {bucket}")
        except S3Error as e:
            logger.error(f"Failed to delete {object_name} from {bucket}: {e}")
            raise

    def file_exists(self, bucket: str, object_name: str) -> bool:
        """
        Check if a file exists in MinIO.

        Args:
            bucket: Bucket name
            object_name: Object key/path in bucket

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.client.stat_object(bucket_name=bucket, object_name=object_name)
            return True
        except S3Error:
            return False


# Global MinIO client instance
minio_client = MinIOClient()
