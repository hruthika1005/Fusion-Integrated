import hashlib
import os
import subprocess
from django.conf import settings
from django.db import transaction
from core.api.exceptions import ConflictError, PermissionDeniedError, NotFoundError
from modules.pms.domain.validators import sanitize_filename, validate_pdf, validate_size
from modules.pms.models import PatentApplication, PmsDocument

def scan_file(path):
    """Run ClamAV when installed. Missing scanner leaves the document quarantined."""
    scanner=getattr(settings,'PMS_ANTIVIRUS_COMMAND','clamdscan')
    try:
        proc=subprocess.run([scanner,'--no-summary',str(path)],capture_output=True,text=True,timeout=60)
    except (FileNotFoundError,subprocess.TimeoutExpired):
        return 'PENDING','Antivirus scanner unavailable or timed out; quarantined.'
    if proc.returncode==0:return 'CLEAN',proc.stdout.strip()
    if proc.returncode==1:return 'INFECTED',proc.stdout.strip() or proc.stderr.strip()
    return 'PENDING','Scanner error; quarantined.'
@transaction.atomic
def attach(*,actor,application,uploaded_file,category,sensitivity='CONFIDENTIAL'):
    if application.applicant_user_id!=actor.user_id and application.assigned_attorney_id!=actor.user_id and not getattr(actor,'has_permission',lambda _:False)('pms.application.view'):
        raise PermissionDeniedError('You cannot attach a document to this application.')
    if not uploaded_file:raise ConflictError('File is required.')
    validate_size(uploaded_file.size)
    head=uploaded_file.read(8); uploaded_file.seek(0)
    filename=sanitize_filename(uploaded_file.name)
    validate_pdf(filename,uploaded_file.content_type,head)
    digest=hashlib.sha256()
    for chunk in uploaded_file.chunks():digest.update(chunk)
    uploaded_file.seek(0)
    previous=PmsDocument.objects.filter(application=application,category=category,is_current=True).order_by('-version').first()
    version=(previous.version+1) if previous else 1
    if previous: previous.is_current=False;previous.save(update_fields=['is_current','updated_at'])
    doc=PmsDocument.objects.create(application=application,uploaded_by_user_id=actor.user_id,category=category,sensitivity=sensitivity,original_filename=filename,file=uploaded_file,checksum_sha256=digest.hexdigest(),version=version)
    status,note=scan_file(doc.file.path)
    doc.scan_status=status;doc.scan_note=note;doc.save(update_fields=['scan_status','scan_note','updated_at'])
    return doc

def download_allowed(actor,doc):
    if doc.scan_status!='CLEAN':raise ConflictError('Document is quarantined until a clean antivirus scan is recorded.')
    if doc.application.applicant_user_id==actor.user_id or doc.application.assigned_director_user_id==actor.user_id or doc.application.assigned_attorney_id==actor.user_id:return True
    if getattr(actor,'has_permission',lambda _:False)('pms.application.view'):return True
    raise NotFoundError('Document not found.')
