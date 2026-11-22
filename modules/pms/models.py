from django.db import models
from django.db.models import Q
from core.db.mixins import TimeStampedModel
from modules.pms.storage import private_storage

class PatentApplication(TimeStampedModel):
    STATUS = [(x,x.replace('_',' ').title()) for x in ['DRAFT','SUBMITTED','RESUBMITTED','UNDER_REVIEW','NEEDS_REVISION','REJECTED','APPROVED','WITHDRAWN','FILED','GRANTED','CLOSED','EXPIRED','APPEAL_SUBMITTED','DECISION_MODIFIED','REJECTION_UPHELD','REMANDED_FOR_AMENDMENT']]
    application_number = models.CharField(max_length=32, unique=True, blank=True)
    applicant_user_id = models.PositiveBigIntegerField(db_index=True)
    title = models.CharField(max_length=300)
    abstract = models.TextField()
    detailed_description = models.TextField()
    claims = models.TextField()
    status = models.CharField(max_length=32, choices=STATUS, default='DRAFT', db_index=True)
    assigned_director_user_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    assigned_attorney_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    attorney_state = models.CharField(max_length=16, default='NONE')
    preferred_attorney_id = models.PositiveBigIntegerField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decision_at = models.DateTimeField(null=True, blank=True)
    resubmission_deadline = models.DateField(null=True, blank=True)
    revision_number = models.PositiveIntegerField(default=0)
    withdrawal_reason = models.TextField(blank=True)
    filing_type = models.CharField(max_length=20, blank=True)
    jurisdiction = models.CharField(max_length=100, blank=True)
    grant_date = models.DateField(null=True, blank=True)
    confidentiality = models.CharField(max_length=20, default='CONFIDENTIAL')
    class Meta:
        db_table='pms_application'
        indexes=[models.Index(fields=['applicant_user_id','created_at'],name='pms_applicant_created_idx'), models.Index(fields=['status','created_at'],name='pms_status_created_idx'), models.Index(fields=['assigned_director_user_id','status'],name='pms_director_status_idx')]

class Inventor(TimeStampedModel):
    application=models.ForeignKey(PatentApplication,on_delete=models.CASCADE,related_name='inventors')
    user_id=models.PositiveBigIntegerField(null=True,blank=True,db_index=True)
    full_name=models.CharField(max_length=200)
    email=models.EmailField(max_length=254)
    ownership_share=models.DecimalField(max_digits=5,decimal_places=2)
    is_applicant=models.BooleanField(default=False)
    consent_status=models.CharField(max_length=20,default='PENDING')
    agreement_signed_at=models.DateTimeField(null=True,blank=True)
    signature_reference=models.CharField(max_length=255,blank=True)
    class Meta:
        db_table='pms_inventor'
        constraints=[models.CheckConstraint(condition=Q(ownership_share__gte=0)&Q(ownership_share__lte=100),name='pms_inv_share_range')]

class PmsDocument(TimeStampedModel):
    application=models.ForeignKey(PatentApplication,on_delete=models.CASCADE,related_name='documents')
    uploaded_by_user_id=models.PositiveBigIntegerField(db_index=True)
    category=models.CharField(max_length=40)
    sensitivity=models.CharField(max_length=20,default='CONFIDENTIAL')
    original_filename=models.CharField(max_length=255)
    file=models.FileField(upload_to='%Y/%m/',max_length=500,storage=private_storage)
    version=models.PositiveIntegerField(default=1)
    is_current=models.BooleanField(default=True)
    checksum_sha256=models.CharField(max_length=64,blank=True)
    scan_status=models.CharField(max_length=16,default='PENDING',db_index=True)
    scan_note=models.TextField(blank=True)
    class Meta:
        db_table='pms_document'
        indexes=[models.Index(fields=['application','category','is_current'],name='pms_doc_app_cat_cur_idx')]

class DirectorReview(TimeStampedModel):
    application=models.ForeignKey(PatentApplication,on_delete=models.CASCADE,related_name='reviews')
    director_user_id=models.PositiveBigIntegerField(db_index=True)
    decision=models.CharField(max_length=20)
    justification=models.TextField()
    cycle=models.PositiveIntegerField(default=1)
    decided_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table='pms_director_review'
        constraints=[models.UniqueConstraint(fields=['application','cycle'],name='pms_review_cycle_unique')]

class AttorneyPanelMember(TimeStampedModel):
    user_id=models.PositiveBigIntegerField(unique=True)
    full_name=models.CharField(max_length=200)
    email=models.EmailField()
    expertise=models.JSONField(default=list,blank=True)
    approved=models.BooleanField(default=True)
    workload=models.PositiveIntegerField(default=0)
    panel_note=models.TextField(blank=True)
    class Meta: db_table='pms_attorney_panel'

class AttorneyAssignment(TimeStampedModel):
    application=models.ForeignKey(PatentApplication,on_delete=models.CASCADE,related_name='attorney_assignments')
    attorney_user_id=models.PositiveBigIntegerField(db_index=True)
    assigned_by_user_id=models.PositiveBigIntegerField()
    status=models.CharField(max_length=20,default='OFFERED')
    response_note=models.TextField(blank=True)
    responded_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        db_table='pms_attorney_assignment'
        constraints=[models.UniqueConstraint(fields=['application','attorney_user_id'],name='pms_attorney_assignment_unique')]

class BudgetRequest(TimeStampedModel):
    application=models.ForeignKey(PatentApplication,on_delete=models.CASCADE,related_name='budgets')
    filing_fees=models.DecimalField(max_digits=12,decimal_places=2,default=0)
    attorney_fees=models.DecimalField(max_digits=12,decimal_places=2,default=0)
    administrative_costs=models.DecimalField(max_digits=12,decimal_places=2,default=0)
    currency=models.CharField(max_length=3,default='INR')
    justification=models.TextField()
    status=models.CharField(max_length=20,default='PENDING')
    requested_by_user_id=models.PositiveBigIntegerField()
    decided_by_user_id=models.PositiveBigIntegerField(null=True,blank=True)
    decision_note=models.TextField(blank=True)
    escalation_required=models.BooleanField(default=False)
    decided_at=models.DateTimeField(null=True,blank=True)
    @property
    def total(self): return self.filing_fees+self.attorney_fees+self.administrative_costs
    class Meta: db_table='pms_budget_request'

class LegalOpinion(TimeStampedModel):
    application=models.ForeignKey(PatentApplication,on_delete=models.CASCADE,related_name='legal_opinions')
    attorney_user_id=models.PositiveBigIntegerField()
    novelty=models.TextField()
    non_obviousness=models.TextField()
    utility=models.TextField()
    opinion=models.TextField()
    recommendation=models.CharField(max_length=24)
    prior_art_references=models.JSONField(default=list,blank=True)
    version=models.PositiveIntegerField(default=1)
    class Meta: db_table='pms_legal_opinion'

class FilingRecord(TimeStampedModel):
    application=models.OneToOneField(PatentApplication,on_delete=models.CASCADE,related_name='filing')
    attorney_user_id=models.PositiveBigIntegerField()
    patent_office=models.CharField(max_length=120)
    external_filing_id=models.CharField(max_length=120)
    filing_date=models.DateField()
    filing_type=models.CharField(max_length=20)
    international_justification=models.TextField(blank=True)
    confirmation_reference=models.CharField(max_length=255,blank=True)
    class Meta: db_table='pms_filing_record'

class OfficeAction(TimeStampedModel):
    application=models.ForeignKey(PatentApplication,on_delete=models.CASCADE,related_name='office_actions')
    patent_office_reference=models.CharField(max_length=120)
    received_date=models.DateField()
    response_deadline=models.DateField(null=True,blank=True)
    description=models.TextField()
    status=models.CharField(max_length=24,default='RECEIVED')
    draft_response=models.TextField(blank=True)
    applicant_approval_required=models.BooleanField(default=False)
    applicant_approved_at=models.DateTimeField(null=True,blank=True)
    submitted_at=models.DateTimeField(null=True,blank=True)
    extension_requested=models.BooleanField(default=False)
    extension_note=models.TextField(blank=True)
    class Meta: db_table='pms_office_action'

class MaintenanceEvent(TimeStampedModel):
    application=models.ForeignKey(PatentApplication,on_delete=models.CASCADE,related_name='maintenance_events')
    jurisdiction=models.CharField(max_length=100)
    due_date=models.DateField()
    fee_amount=models.DecimalField(max_digits=12,decimal_places=2,null=True,blank=True)
    renewal_decision=models.CharField(max_length=20,default='PENDING')
    decision_by_user_id=models.PositiveBigIntegerField(null=True,blank=True)
    decision_at=models.DateTimeField(null=True,blank=True)
    completion_reference=models.CharField(max_length=255,blank=True)
    completed_at=models.DateTimeField(null=True,blank=True)
    notes=models.TextField(blank=True)
    class Meta: db_table='pms_maintenance_event'

class LicenseRequest(TimeStampedModel):
    application=models.ForeignKey(PatentApplication,on_delete=models.CASCADE,related_name='license_requests')
    requested_by_user_id=models.PositiveBigIntegerField()
    organization=models.CharField(max_length=200)
    request_type=models.CharField(max_length=30,default='LICENSING')
    details=models.TextField()
    status=models.CharField(max_length=20,default='SUBMITTED')
    reviewed_by_user_id=models.PositiveBigIntegerField(null=True,blank=True)
    review_note=models.TextField(blank=True)
    reviewed_at=models.DateTimeField(null=True,blank=True)
    class Meta: db_table='pms_license_request'

class Appeal(TimeStampedModel):
    application=models.ForeignKey(PatentApplication,on_delete=models.CASCADE,related_name='appeals')
    applicant_user_id=models.PositiveBigIntegerField()
    grounds=models.TextField()
    filed_at=models.DateTimeField(auto_now_add=True)
    status=models.CharField(max_length=24,default='SUBMITTED')
    outcome=models.CharField(max_length=24,blank=True)
    reviewed_by_user_id=models.PositiveBigIntegerField(null=True,blank=True)
    review_note=models.TextField(blank=True)
    reviewed_at=models.DateTimeField(null=True,blank=True)
    class Meta: db_table='pms_appeal'

class PriorArtReference(TimeStampedModel):
    application=models.ForeignKey(PatentApplication,on_delete=models.CASCADE,related_name='prior_art')
    added_by_user_id=models.PositiveBigIntegerField()
    title=models.CharField(max_length=300)
    reference_url=models.URLField(max_length=1000)
    source=models.CharField(max_length=120,blank=True)
    notes=models.TextField(blank=True)
    class Meta: db_table='pms_prior_art'

class Deadline(TimeStampedModel):
    application=models.ForeignKey(PatentApplication,on_delete=models.CASCADE,related_name='deadlines')
    kind=models.CharField(max_length=40)
    due_date=models.DateField()
    responsible_user_id=models.PositiveBigIntegerField(null=True,blank=True)
    status=models.CharField(max_length=16,default='OPEN')
    completed_at=models.DateTimeField(null=True,blank=True)
    source_record_type=models.CharField(max_length=40,blank=True)
    source_record_id=models.PositiveBigIntegerField(null=True,blank=True)
    notes=models.TextField(blank=True)
    class Meta: db_table='pms_deadline'; indexes=[models.Index(fields=['status','due_date'],name='pms_deadline_status_due_idx')]

class AuditEvent(models.Model):
    at=models.DateTimeField(auto_now_add=True,db_index=True)
    actor_user_id=models.PositiveBigIntegerField(null=True,blank=True,db_index=True)
    actor_role=models.CharField(max_length=32,blank=True)
    application=models.ForeignKey(PatentApplication,on_delete=models.SET_NULL,null=True,blank=True,related_name='audit_events')
    action=models.CharField(max_length=80)
    entity_type=models.CharField(max_length=60)
    entity_id=models.PositiveBigIntegerField(null=True,blank=True)
    previous_state=models.JSONField(null=True,blank=True)
    new_state=models.JSONField(null=True,blank=True)
    metadata=models.JSONField(default=dict,blank=True)
    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValueError('AuditEvent records are append-only.')
        return super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        raise ValueError('AuditEvent records are append-only.')
    class Meta: db_table='pms_audit_event'; ordering=['at']
