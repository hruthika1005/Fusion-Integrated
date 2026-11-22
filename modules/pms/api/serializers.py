from rest_framework import serializers
from modules.pms.models import PatentApplication, Inventor, PmsDocument, DirectorReview, AttorneyPanelMember, AttorneyAssignment, BudgetRequest, LegalOpinion, FilingRecord, OfficeAction, MaintenanceEvent, LicenseRequest, Appeal, PriorArtReference, Deadline, AuditEvent

class InventorInput(serializers.Serializer):
    user_id=serializers.IntegerField(required=False,allow_null=True)
    full_name=serializers.CharField(max_length=200)
    email=serializers.EmailField()
    ownership_share=serializers.DecimalField(max_digits=5,decimal_places=2)
    is_applicant=serializers.BooleanField(default=False)
    consent_status=serializers.ChoiceField(choices=['PENDING','SIGNED','DECLINED'],default='PENDING')

class ApplicationCreate(serializers.Serializer):
    title=serializers.CharField(max_length=300)
    abstract=serializers.CharField()
    detailed_description=serializers.CharField()
    claims=serializers.CharField()
    inventors=InventorInput(many=True,required=False)

class InventorSerializer(serializers.ModelSerializer):
    class Meta:
        model=Inventor
        fields='__all__'
        read_only_fields=fields

class ApplicationSerializer(serializers.ModelSerializer):
    inventors=InventorSerializer(many=True,read_only=True)
    class Meta:
        model=PatentApplication
        fields='__all__'
        read_only_fields=fields

class ReviewInput(serializers.Serializer):
    decision=serializers.ChoiceField(choices=['APPROVED','REJECTED','NEEDS_REVISION'])
    justification=serializers.CharField()

class AssignDirectorInput(serializers.Serializer):
    director_user_id=serializers.IntegerField(min_value=1)

class AttorneyInput(serializers.Serializer):
    attorney_user_id=serializers.IntegerField(min_value=1)

class AttorneyResponseInput(serializers.Serializer):
    accept=serializers.BooleanField()
    note=serializers.CharField(required=False,allow_blank=True)

class BudgetInput(serializers.Serializer):
    filing_fees=serializers.DecimalField(max_digits=12,decimal_places=2,default=0)
    attorney_fees=serializers.DecimalField(max_digits=12,decimal_places=2,default=0)
    administrative_costs=serializers.DecimalField(max_digits=12,decimal_places=2,default=0)
    currency=serializers.CharField(max_length=3,default='INR')
    justification=serializers.CharField()
class BudgetDecisionInput(serializers.Serializer):
    decision=serializers.ChoiceField(choices=['APPROVED','REJECTED','ESCALATED'])
    note=serializers.CharField(required=False,allow_blank=True)
class LegalOpinionInput(serializers.Serializer):
    novelty=serializers.CharField()
    non_obviousness=serializers.CharField()
    utility=serializers.CharField()
    opinion=serializers.CharField()
    recommendation=serializers.ChoiceField(choices=['File Patent','Do Not File','Needs Amendment'])
    prior_art_references=serializers.ListField(child=serializers.DictField(),required=False)
class FilingInput(serializers.Serializer):
    patent_office=serializers.CharField(max_length=120)
    external_filing_id=serializers.CharField(max_length=120)
    filing_date=serializers.DateField()
    filing_type=serializers.ChoiceField(choices=['National','International'])
    international_justification=serializers.CharField(required=False,allow_blank=True)
    confirmation_reference=serializers.CharField(max_length=255)
class OfficeActionInput(serializers.Serializer):
    patent_office_reference=serializers.CharField(max_length=120)
    received_date=serializers.DateField()
    response_deadline=serializers.DateField(required=False,allow_null=True)
    description=serializers.CharField()
    applicant_approval_required=serializers.BooleanField(default=False)
class OfficeResponseInput(serializers.Serializer):
    response_text=serializers.CharField()
class AppealInput(serializers.Serializer):
    grounds=serializers.CharField()
class AppealDecisionInput(serializers.Serializer):
    outcome=serializers.ChoiceField(choices=['UPHELD','REVERSED','REMANDED'])
    note=serializers.CharField(required=False,allow_blank=True)
class AttorneyPanelInput(serializers.Serializer):
    user_id=serializers.IntegerField(min_value=1)
    full_name=serializers.CharField(max_length=200)
    email=serializers.EmailField()
    expertise=serializers.ListField(child=serializers.CharField(),required=False)
    approved=serializers.BooleanField(default=True)
    panel_note=serializers.CharField(required=False,allow_blank=True)
class PriorArtInput(serializers.Serializer):
    title=serializers.CharField(max_length=300)
    reference_url=serializers.URLField(max_length=1000)
    source=serializers.CharField(max_length=120,required=False,allow_blank=True)
    notes=serializers.CharField(required=False,allow_blank=True)
class LicenseInput(serializers.Serializer):
    organization=serializers.CharField(max_length=200)
    request_type=serializers.ChoiceField(choices=['LICENSING','TECHNOLOGY_TRANSFER'])
    details=serializers.CharField()
class LicenseDecisionInput(serializers.Serializer):
    status=serializers.ChoiceField(choices=['APPROVED','REJECTED','MORE_INFORMATION'])
    note=serializers.CharField(required=False,allow_blank=True)
class MaintenanceDecisionInput(serializers.Serializer):
    renewal_decision=serializers.ChoiceField(choices=['RENEW','DO_NOT_RENEW'])
    notes=serializers.CharField(required=False,allow_blank=True)
class DeadlineSerializer(serializers.ModelSerializer):
    class Meta:
        model=Deadline
        fields='__all__'
class AuditSerializer(serializers.ModelSerializer):
    class Meta:
        model=AuditEvent
        fields='__all__'
class AttorneyAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model=AttorneyAssignment
        fields='__all__'
        read_only_fields=fields
class RevisionInput(serializers.Serializer):
    title=serializers.CharField(max_length=300,required=False)
    abstract=serializers.CharField(required=False)
    detailed_description=serializers.CharField(required=False)
    claims=serializers.CharField(required=False)
class MaintenanceCreateInput(serializers.Serializer):
    jurisdiction=serializers.CharField(max_length=100)
    due_date=serializers.DateField()
    fee_amount=serializers.DecimalField(max_digits=12,decimal_places=2,required=False,allow_null=True)
    notes=serializers.CharField(required=False,allow_blank=True)
class MaintenanceCompletionInput(serializers.Serializer):
    completion_reference=serializers.CharField(max_length=255)
