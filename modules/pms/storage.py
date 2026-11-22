from django.conf import settings
from django.core.files.storage import FileSystemStorage
from pathlib import Path

def private_storage():
    """PMS private filesystem storage. No public URL is generated."""
    root=Path(getattr(settings,'PMS_UPLOAD_ROOT',Path.home()/'.local/share/fusion-integrated/pms'))
    root.mkdir(parents=True,exist_ok=True)
    return FileSystemStorage(location=str(root),base_url=None)
