"""MinIO client for file storage operations."""

import logging
from io import BytesIO
from urllib.parse import urlparse
from minio import Minio
from minio.error import S3Error

from app.core.config import settings

logger = logging.getLogger(__name__)


class MinIOClient:
    """MinIO S3-compatible object storage client."""

    def __init__(self):
        """
        Initialize the MinIO client using application configuration.

        Creates and stores a configured Minio SDK client on the instance and sets
        the `bucket_blackbox` and `bucket_assets` attributes to the configured
        bucket names from settings.
        """
        # Parse URL to detect scheme and set secure flag
        parsed_url = urlparse(settings.minio_public_url)
        secure = parsed_url.scheme == "https"
        endpoint = settings.minio_public_url.replace("http://", "").replace("https://", "")

        self.client = Minio(
            endpoint,
            access_key=settings.minio_root_user,
            secret_key=settings.minio_root_password,
            secure=secure,
        )
        self.bucket_blackbox = settings.minio_bucket_blackbox_logs
        self.bucket_assets = settings.minio_bucket_assets

    def upload_file(
        self, bucket: str, object_name: str, file_content: bytes
    ) -> str:
        """
        Upload a file to the specified MinIO bucket.
        
        Parameters:
            bucket (str): Destination bucket name.
            object_name (str): Key/path for the object inside the bucket.
            file_content (bytes): File content to upload.
        
        Returns:
            str: `object_name` of the uploaded object.
        
        Raises:
            S3Error: If the upload fails.
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
        Download an object from MinIO and return its contents.

        Parameters:
            bucket (str): Name of the bucket.
            object_name (str): Object key or path within the bucket.

        Returns:
            bytes: The object's content.

        Raises:
            S3Error: If the object cannot be retrieved.
        """
        response = None
        try:
            response = self.client.get_object(bucket_name=bucket, object_name=object_name)
            content = response.read()
            logger.info(f"Downloaded {object_name} from {bucket}")
            return content
        except S3Error as e:
            logger.error(f"Failed to download {object_name} from {bucket}: {e}")
            raise
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def delete_file(self, bucket: str, object_name: str) -> None:
        """
        Delete an object from the given MinIO bucket.
        
        Parameters:
            bucket (str): Name of the target bucket.
            object_name (str): Key or path of the object to delete.
        
        Raises:
            S3Error: If the MinIO deletion operation fails.
        """
        try:
            self.client.remove_object(bucket_name=bucket, object_name=object_name)
            logger.info(f"Deleted {object_name} from {bucket}")
        except S3Error as e:
            logger.error(f"Failed to delete {object_name} from {bucket}: {e}")
            raise

    def file_exists(self, bucket: str, object_name: str) -> bool:
        """
        Determine whether an object with the given name exists in the specified bucket.

        Parameters:
            bucket (str): Name of the bucket to check.
            object_name (str): Object key or path within the bucket.

        Returns:
            `true` if the object exists in the bucket, `false` otherwise.

        Raises:
            S3Error: If the check fails for reasons other than the object not existing.
        """
        try:
            self.client.stat_object(bucket_name=bucket, object_name=object_name)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            raise


# Global MinIO client instance
minio_client = MinIOClient()