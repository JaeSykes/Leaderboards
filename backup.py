"""
Google Drive Backup System for Stats Database
Automatic daily backups at 3 AM CET
"""

import os
import shutil
import logging
from datetime import datetime, timedelta
from pathlib import Path

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GDRIVE_AVAILABLE = True
except ImportError:
    GDRIVE_AVAILABLE = False

logger = logging.getLogger(__name__)

# Google Drive configuration
GDRIVE_FOLDER_ID = os.getenv('GDRIVE_BACKUP_FOLDER_ID')  # Set in Railway env
SERVICE_ACCOUNT_JSON = 'credentials/google_service_account.json'
DB_PATH = 'data/stats.db'
BACKUP_DIR = 'backups'
MAX_LOCAL_BACKUPS = 7  # Keep 7 days locally


class GoogleDriveBackup:
    """Handle backups to Google Drive"""
    
    def __init__(self):
        self.service = None
        self.folder_id = GDRIVE_FOLDER_ID
        
        if not GDRIVE_AVAILABLE:
            logger.warning('⚠️ Google Drive API not available (optional feature)')
            return
        
        try:
            self._authenticate()
        except Exception as e:
            logger.warning(f'⚠️ Google Drive auth failed: {e}')
    
    def _authenticate(self):
        """Authenticate with Google Drive using service account"""
        if not os.path.exists(SERVICE_ACCOUNT_JSON):
            logger.warning(f'⚠️ Service account file not found: {SERVICE_ACCOUNT_JSON}')
            return
        
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_JSON,
            scopes=['https://www.googleapis.com/auth/drive']
        )
        
        self.service = build('drive', 'v3', credentials=credentials)
        logger.info('✅ Google Drive authenticated')
    
    def upload_backup(self, file_path: str, file_name: str) -> bool:
        """Upload backup to Google Drive"""
        if not self.service or not self.folder_id:
            logger.debug('🔍 Google Drive backup skipped (not configured)')
            return False
        
        try:
            file_metadata = {
                'name': file_name,
                'parents': [self.folder_id],
                'description': f'Stats DB backup from {datetime.now().isoformat()}'
            }
            
            media = MediaFileUpload(
                file_path,
                mimetype='application/octet-stream',
                resumable=True
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            logger.info(f'✅ Google Drive backup uploaded: {file_name} (ID: {file["id"]})')
            return True
        
        except Exception as e:
            logger.error(f'❌ Google Drive upload failed: {e}')
            return False
    
    def list_backups(self, limit: int = 10) -> list:
        """List backups in Google Drive"""
        if not self.service or not self.folder_id:
            return []
        
        try:
            results = self.service.files().list(
                q=f"'{self.folder_id}' in parents and trashed=false",
                spaces='drive',
                fields='files(id, name, createdTime)',
                pageSize=limit,
                orderBy='createdTime desc'
            ).execute()
            
            return results.get('files', [])
        
        except Exception as e:
            logger.error(f'❌ Failed to list backups: {e}')
            return []
    
    def download_backup(self, file_id: str, output_path: str) -> bool:
        """Download backup from Google Drive"""
        if not self.service:
            return False
        
        try:
            request = self.service.files().get_media(fileId=file_id)
            
            with open(output_path, 'wb') as f:
                f.write(request.execute())
            
            logger.info(f'✅ Backup downloaded: {output_path}')
            return True
        
        except Exception as e:
            logger.error(f'❌ Download failed: {e}')
            return False


class LocalBackup:
    """Handle local backups"""
    
    @staticmethod
    def create_backup() -> str:
        """Create local backup and return path"""
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f'stats_backup_{timestamp}.db'
            backup_path = os.path.join(BACKUP_DIR, backup_name)
            
            if not os.path.exists(DB_PATH):
                logger.warning(f'⚠️ Database not found: {DB_PATH}')
                return None
            
            shutil.copy2(DB_PATH, backup_path)
            logger.info(f'✅ Local backup created: {backup_path}')
            
            return backup_path
        
        except Exception as e:
            logger.error(f'❌ Local backup failed: {e}')
            return None
    
    @staticmethod
    def cleanup_old_backups():
        """Keep only MAX_LOCAL_BACKUPS recent backups"""
        try:
            if not os.path.exists(BACKUP_DIR):
                return
            
            backups = sorted(
                Path(BACKUP_DIR).glob('stats_backup_*.db'),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            for old_backup in backups[MAX_LOCAL_BACKUPS:]:
                old_backup.unlink()
                logger.info(f'🗑️ Deleted old backup: {old_backup.name}')
        
        except Exception as e:
            logger.error(f'❌ Cleanup failed: {e}')
    
    @staticmethod
    def restore_backup(backup_path: str) -> bool:
        """Restore database from backup"""
        try:
            if not os.path.exists(backup_path):
                logger.error(f'❌ Backup not found: {backup_path}')
                return False
            
            # Create safety backup of current DB
            if os.path.exists(DB_PATH):
                safety_backup = f'{DB_PATH}.safety_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
                shutil.copy2(DB_PATH, safety_backup)
                logger.info(f'✅ Safety backup created: {safety_backup}')
            
            # Restore
            shutil.copy2(backup_path, DB_PATH)
            logger.info(f'✅ Database restored from: {backup_path}')
            return True
        
        except Exception as e:
            logger.error(f'❌ Restore failed: {e}')
            return False


async def perform_backup():
    """Execute full backup routine (local + Google Drive)"""
    logger.info('⏳ Starting backup routine...')
    
    # Local backup
    local_path = LocalBackup.create_backup()
    if not local_path:
        logger.error('❌ Backup routine failed')
        return
    
    # Cleanup old local backups
    LocalBackup.cleanup_old_backups()
    
    # Google Drive backup
    if GDRIVE_AVAILABLE and GDRIVE_FOLDER_ID:
        gdrive = GoogleDriveBackup()
        backup_name = os.path.basename(local_path)
        gdrive.upload_backup(local_path, backup_name)
        
        # Log stats
        backups = gdrive.list_backups(limit=5)
        logger.info(f'📊 Backups in Google Drive: {len(backups)}')
        for backup in backups:
            logger.debug(f'   - {backup["name"]} ({backup["createdTime"]})')
    else:
        logger.info('ℹ️ Google Drive backup skipped (not configured)')
    
    logger.info('✅ Backup routine completed')


def setup_backup_scheduler(bot):
    """Setup daily backup scheduler (3 AM CET)"""
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        
        scheduler = AsyncIOScheduler()
        
        # Daily backup at 3 AM CET
        scheduler.add_job(
            perform_backup,
            trigger=CronTrigger(hour=3, minute=0, timezone='Europe/Prague'),
            id='daily_backup',
            name='Daily Database Backup',
            replace_existing=True
        )
        
        scheduler.start()
        logger.info('✅ Backup scheduler configured: Daily at 3:00 AM CET')
        
    except Exception as e:
        logger.error(f'❌ Failed to setup backup scheduler: {e}')
