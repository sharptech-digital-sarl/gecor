import os
import aiofiles
from pathlib import Path
from typing import BinaryIO, Optional
from app.core.config import settings


class StorageService:
    """Hybrid storage service supporting local filesystem and S3-compatible storage"""
    
    def __init__(self):
        self.storage_type = settings.STORAGE_TYPE
        self.storage_path = settings.STORAGE_PATH
        
        if self.storage_type == "local":
            # Ensure storage directory exists
            Path(self.storage_path).mkdir(parents=True, exist_ok=True)
    
    async def save_file(
        self,
        file_content: bytes,
        file_name: str,
        subdirectory: Optional[str] = None
    ) -> str:
        """Save file and return relative path"""
        if self.storage_type == "local":
            return await self._save_local(file_content, file_name, subdirectory)
        elif self.storage_type == "s3":
            return await self._save_s3(file_content, file_name, subdirectory)
        else:
            raise ValueError(f"Unsupported storage type: {self.storage_type}")
    
    async def _save_local(
        self,
        file_content: bytes,
        file_name: str,
        subdirectory: Optional[str] = None
    ) -> str:
        """Save file to local filesystem"""
        if subdirectory:
            file_dir = Path(self.storage_path) / subdirectory
        else:
            file_dir = Path(self.storage_path)
        
        file_dir.mkdir(parents=True, exist_ok=True)
        file_path = file_dir / file_name
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)
        
        # Return relative path from storage root
        if subdirectory:
            return f"{subdirectory}/{file_name}"
        return file_name
    
    async def _save_s3(
        self,
        file_content: bytes,
        file_name: str,
        subdirectory: Optional[str] = None
    ) -> str:
        """Save file to S3-compatible storage (MinIO)"""
        try:
            from minio import Minio
            from minio.error import S3Error
            
            client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=False
            )
            
            # Ensure bucket exists
            if not client.bucket_exists(settings.MINIO_BUCKET):
                client.make_bucket(settings.MINIO_BUCKET)
            
            object_name = f"{subdirectory}/{file_name}" if subdirectory else file_name
            
            from io import BytesIO
            client.put_object(
                settings.MINIO_BUCKET,
                object_name,
                BytesIO(file_content),
                length=len(file_content)
            )
            
            return object_name
        except Exception as e:
            raise Exception(f"Failed to save to S3: {str(e)}")
    
    async def get_file(self, file_path: str) -> bytes:
        """Retrieve file content"""
        if self.storage_type == "local":
            return await self._get_local(file_path)
        elif self.storage_type == "s3":
            return await self._get_s3(file_path)
        else:
            raise ValueError(f"Unsupported storage type: {self.storage_type}")
    
    async def _get_local(self, file_path: str) -> bytes:
        """Get file from local filesystem"""
        full_path = Path(self.storage_path) / file_path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        async with aiofiles.open(full_path, 'rb') as f:
            return await f.read()
    
    async def _get_s3(self, file_path: str) -> bytes:
        """Get file from S3-compatible storage"""
        try:
            from minio import Minio
            from io import BytesIO
            
            client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=False
            )
            
            response = client.get_object(settings.MINIO_BUCKET, file_path)
            return response.read()
        except Exception as e:
            raise Exception(f"Failed to get from S3: {str(e)}")
    
    def delete_file(self, file_path: str) -> bool:
        """Delete file"""
        if self.storage_type == "local":
            full_path = Path(self.storage_path) / file_path
            if full_path.exists():
                full_path.unlink()
                return True
            return False
        elif self.storage_type == "s3":
            try:
                from minio import Minio
                client = Minio(
                    settings.MINIO_ENDPOINT,
                    access_key=settings.MINIO_ACCESS_KEY,
                    secret_key=settings.MINIO_SECRET_KEY,
                    secure=False
                )
                client.remove_object(settings.MINIO_BUCKET, file_path)
                return True
            except Exception as e:
                raise Exception(f"Failed to delete from S3: {str(e)}")
        else:
            raise ValueError(f"Unsupported storage type: {self.storage_type}")


storage_service = StorageService()

