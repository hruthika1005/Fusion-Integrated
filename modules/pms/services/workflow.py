from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from core.api.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from modules.pms.domain import validators, ownership
from modules.pms.models import (PatentApplication, Inventor, DirectorReview, AttorneyPanelMember,
 AttorneyAssignment, BudgetRequest, LegalOpinion, FilingRecord, OfficeAction, MaintenanceEvent,
 LicenseRequest, Appeal, PriorArtReference, Deadline, AuditEvent)

ROLE_PERMISSION={
 'APPLICANT':'pms.application.submit','DIRECTOR':'pms.application.review','PCC_ADMIN':'pms.application.assign_director',
 'ATTORNEY':'pms.legal.assess'
}
def role(actor):
    active=(getattr(actor,'active_role',None) or '').upper()
    roles={str(r).upper() for r in getattr(actor,'roles',())}
    for candidate in ('PCC_ADMIN','DIRECTOR','ATTORNEY','APPLICANT'):
        if active==candidate or candidate in roles:return candidate
    return 'APPLICANT'
def has(actor, code):
    checker=getattr(actor,'has_permission',None)
    return bool(checker and checker(code))
def require(actor, code):
    if actor is None or not has(actor,code): raise PermissionDeniedError('Permission required: '+code)
def visible_applications(actor):
    qs=PatentApplication.objects.all()
    if has(actor,'pms.application.view') or has(actor,'pms.application.assign_director') or has(actor,'pms.configuration.manage'):
        return qs
    if has(actor,'pms.application.review'):
        return qs.filter(assigned_director_user_id=actor.user_id)
    if has(actor,'pms.legal.assess') or has(actor,'pms.filing.manage'):
        return qs.filter(assigned_attorney_id=actor.user_id)
    return qs.filter(applicant_user_id=actor.user_id)
def audit(actor, app, action, entity, entity_id=None, old=None, new=None, metadata=None):
    AuditEvent.objects.create(actor_user_id=getattr(actor,'user_id',None),actor_role=role(actor),application=app,
      action=action,entity_type=entity,entity_id=entity_id,previous_state=old,new_state=new,metadata=metadata or {})
@transaction.atomic
def create_application(actor, data):
    validators.validate_submission_complete(data, [{**i, 'ownership_percentage': i.get('ownership_share')} for i in (data.get('inventors') or [{'full_name':getattr(actor,'display_name','Applicant'),'email':getattr(actor,'email',''),'ownership_share':100}])])
    app=PatentApplication.objects.create(applicant_user_id=actor.user_id,**{k:data[k] for k in ('title','abstract','detailed_description','claims')})
    app.application_number=f'PMS-{timezone.now():%Y}-{app.pk:06d}'
    app.save(update_fields=['application_number','updated_at'])
    inventors=data.get('inventors') or [{'user_id':actor.user_id,'full_name':getattr(actor,'display_name','Applicant'),'email':getattr(actor,'email',''),'ownership_share':100,'is_applicant':True}]
    ownership.validate_shares([i.get('ownership_share') for i in inventors])
    for inv in inventors:
        validators.validate_inventor(inv.get('full_name'),inv.get('email'))
        Inventor.objects.create(application=app,**inv)
    audit(actor,app,'APPLICATION_CREATED','PatentApplication',app.pk,new={'status':app.status})
    return app
@transaction.atomic
def submit(actor, app):
    if app.applicant_user_id!=actor.user_id: raise PermissionDeniedError('Only the applicant may submit this application.')
    if app.status not in ('DRAFT','NEEDS_REVISION','REJECTED'): raise ConflictError('Application cannot be submitted from its current state.')
    if not app.inventors.exists(): raise ConflictError('Inventor information is required.')
    if any(i.consent_status!='SIGNED' for i in app.inventors.all()): raise ConflictError('All inventor agreements/consents must be completed before submission.')
    old=app.status; app.status='SUBMITTED' if old=='DRAFT' else 'RESUBMITTED'; app.submitted_at=timezone.now(); app.revision_number+=1
    app.save(update_fields=['status','submitted_at','revision_number','updated_at'])
    audit(actor,app,'APPLICATION_SUBMITTED','PatentApplication',app.pk,old={'status':old},new={'status':app.status,'revision':app.revision_number})
    return app
@transaction.atomic
def assign_director(actor, app, director_id, expertise=None):
    require(actor,'pms.application.assign_director')
    if app.status not in ('SUBMITTED','RESUBMITTED'): raise ConflictError('Only submitted applications can be assigned.')
    if any(i.user_id==director_id for i in app.inventors.all()): raise ConflictError('Director is an inventor; conflict of interest.')
    if any(i.user_id==actor.user_id for i in app.inventors.all()): raise ConflictError('PCC_ADMIN is an inventor; conflict of interest.')
    old=app.status; app.assigned_director_user_id=director_id; app.status='UNDER_REVIEW'; app.save(update_fields=['assigned_director_user_id','status','updated_at'])
    audit(actor,app,'DIRECTOR_ASSIGNED','PatentApplication',app.pk,old={'status':old},new={'status':app.status,'director_user_id':director_id})
    due=timezone.localdate(); business_days=0
    while business_days<15:
        due+=timedelta(days=1)
        if due.weekday()<5: business_days+=1
    Deadline.objects.create(application=app,kind='DIRECTOR_REVIEW',due_date=due,responsible_user_id=director_id,notes='15 business days; public holidays are not excluded because no holiday calendar is configured.')
    return app
@transaction.atomic
def review(actor, app, decision, justification):
    require(actor,'pms.application.review')
    if app.assigned_director_user_id!=actor.user_id: raise PermissionDeniedError('Application is not assigned to this Director.')
    if app.status!='UNDER_REVIEW': raise ConflictError('Application is not under review.')
    validators.validate_justification(justification); validators.validate_decision(decision)
    target={'APPROVED':'APPROVED','REJECTED':'REJECTED','NEEDS_REVISION':'NEEDS_REVISION'}[decision]
    old=app.status; app.status=target; app.decision_at=timezone.now()
    if target in ('NEEDS_REVISION','REJECTED'): app.resubmission_deadline=timezone.localdate()+timedelta(days=60)
    app.save(update_fields=['status','decision_at','resubmission_deadline','updated_at'])
    DirectorReview.objects.create(application=app,director_user_id=actor.user_id,decision=decision,justification=justification,cycle=max(1,app.revision_number))
    audit(actor,app,'DIRECTOR_DECISION','DirectorReview',app.pk,old={'status':old},new={'status':target,'decision':decision,'justification':justification})
    return app
@transaction.atomic
def assign_attorney(actor, app, attorney_id):
    require(actor,'pms.attorney.manage')
    if app.status!='APPROVED': raise ConflictError('Attorney assignment requires an approved application.')
    panel=AttorneyPanelMember.objects.filter(user_id=attorney_id,approved=True).first()
    if panel is None: raise ConflictError('Attorney must belong to the approved panel.')
    if any(i.user_id==attorney_id for i in app.inventors.all()): raise ConflictError('Attorney conflict of interest.')
    if AttorneyAssignment.objects.filter(application=app,status='ACCEPTED').exists(): raise ConflictError('An attorney is already assigned.')
    AttorneyAssignment.objects.create(application=app,attorney_user_id=attorney_id,assigned_by_user_id=actor.user_id)
    app.assigned_attorney_id=attorney_id; app.attorney_state='OFFERED'; app.save(update_fields=['assigned_attorney_id','attorney_state','updated_at'])
    audit(actor,app,'ATTORNEY_OFFERED','AttorneyAssignment',app.pk,new={'attorney_user_id':attorney_id})
    return app
@transaction.atomic
def attorney_response(actor, assignment, accept, note=''):
    require(actor,'pms.attorney.respond')
    if assignment.attorney_user_id!=actor.user_id: raise PermissionDeniedError('Assignment is not addressed to you.')
    if assignment.status!='OFFERED': raise ConflictError('Assignment already responded to.')
    assignment.status='ACCEPTED' if accept else 'DECLINED'; assignment.response_note=note; assignment.responded_at=timezone.now(); assignment.save()
    app=assignment.application; app.attorney_state=assignment.status; app.assigned_attorney_id=actor.user_id if accept else None; app.save(update_fields=['attorney_state','assigned_attorney_id','updated_at'])
    audit(actor,app,'ATTORNEY_RESPONSE','AttorneyAssignment',assignment.pk,new={'status':assignment.status,'note':note})
    return assignment
@transaction.atomic
def request_budget(actor, app, data):
    require(actor,'pms.budget.review')
    if app.status!='APPROVED': raise ConflictError('Budget can be requested only after application approval.')
    vals=[Decimal(str(data.get(k,0))) for k in ('filing_fees','attorney_fees','administrative_costs')]
    if any(v<0 for v in vals): raise ConflictError('Budget amounts cannot be negative.')
    obj=BudgetRequest.objects.create(application=app,filing_fees=vals[0],attorney_fees=vals[1],administrative_costs=vals[2],currency=data.get('currency','INR'),justification=data['justification'],requested_by_user_id=actor.user_id)
    audit(actor,app,'BUDGET_REQUESTED','BudgetRequest',obj.pk,new={'total':str(obj.total)})
    return obj
@transaction.atomic
def budget_decision(actor, budget, decision, note=''):
    require(actor,'pms.budget.review')
    if budget.status!='PENDING': raise ConflictError('Budget request already decided.')
    budget.status=decision; budget.decided_by_user_id=actor.user_id; budget.decision_note=note; budget.decided_at=timezone.now(); budget.save()
    audit(actor,budget.application,'BUDGET_DECISION','BudgetRequest',budget.pk,new={'status':decision,'note':note,'total':str(budget.total)})
    return budget
@transaction.atomic
def legal_opinion(actor, app, data):
    require(actor,'pms.legal.assess')
    if app.assigned_attorney_id!=actor.user_id or app.attorney_state!='ACCEPTED': raise PermissionDeniedError('Accepted attorney assignment required.')
    validators.validate_recommendation(data['recommendation'])
    opinion=LegalOpinion.objects.create(application=app,attorney_user_id=actor.user_id,**data,version=app.legal_opinions.count()+1)
    audit(actor,app,'LEGAL_OPINION_RECORDED','LegalOpinion',opinion.pk,new={'recommendation':opinion.recommendation})
    return opinion
@transaction.atomic
def record_filing(actor, app, data):
    require(actor,'pms.filing.manage')
    if app.status!='APPROVED' or app.assigned_attorney_id!=actor.user_id: raise ConflictError('Only assigned attorney may file an approved application.')
    latest_opinion=app.legal_opinions.order_by('-version').first()
    if latest_opinion is None or latest_opinion.recommendation!='File Patent': raise ConflictError('A current legal opinion recommending filing is required.')
    if not app.inventors.exists() or any(i.consent_status!='SIGNED' for i in app.inventors.all()): raise ConflictError('Inventor agreement prerequisite is not satisfied.')
    validators.validate_filing_details(data.get('filing_type'), data.get('international_justification',''))
    validators.validate_filing_identifiers(data.get('external_filing_id'), data.get('filing_date'), data.get('confirmation_reference'))
    f=FilingRecord.objects.create(application=app,attorney_user_id=actor.user_id,**data)
    app.status='FILED'; app.save(update_fields=['status','updated_at']); audit(actor,app,'FILING_RECORDED','FilingRecord',f.pk,new={'status':'FILED','external_id':f.external_filing_id})
    return f
@transaction.atomic
def record_office_action(actor, app, data):
    require(actor,'pms.office_action.manage')
    if app.assigned_attorney_id!=actor.user_id: raise PermissionDeniedError('Assigned attorney required.')
    obj=OfficeAction.objects.create(application=app,**data)
    if obj.response_deadline: Deadline.objects.create(application=app,kind='OFFICE_ACTION_RESPONSE',due_date=obj.response_deadline,responsible_user_id=actor.user_id,source_record_type='OfficeAction',source_record_id=obj.pk)
    audit(actor,app,'OFFICE_ACTION_RECORDED','OfficeAction',obj.pk,new={'deadline':str(obj.response_deadline) if obj.response_deadline else None})
    return obj
@transaction.atomic
def submit_office_response(actor, office_action, response_text):
    require(actor,'pms.office_action.manage')
    if office_action.application.assigned_attorney_id!=actor.user_id: raise PermissionDeniedError('Assigned attorney required.')
    if not response_text.strip(): raise ConflictError('Response draft is required.')
    if office_action.applicant_approval_required and not office_action.applicant_approved_at: raise ConflictError('Applicant approval is required before submission.')
    office_action.draft_response=response_text; office_action.status='SUBMITTED'; office_action.submitted_at=timezone.now(); office_action.save()
    audit(actor,office_action.application,'OFFICE_ACTION_RESPONSE_SUBMITTED','OfficeAction',office_action.pk,new={'status':'SUBMITTED'})
    return office_action
@transaction.atomic
def create_appeal(actor, app, grounds):
    require(actor,'pms.application.submit')
    if app.applicant_user_id!=actor.user_id or app.status!='REJECTED': raise ConflictError('Appeal is allowed only by applicant after rejection.')
    validators.validate_grounds(grounds)
    obj=Appeal.objects.create(application=app,applicant_user_id=actor.user_id,grounds=grounds)
    app.status='APPEAL_SUBMITTED'; app.save(update_fields=['status','updated_at']); audit(actor,app,'APPEAL_SUBMITTED','Appeal',obj.pk,new={'status':app.status})
    return obj
@transaction.atomic
def decide_appeal(actor, appeal, outcome, note):
    require(actor,'pms.appeal.review')
    if appeal.status!='SUBMITTED': raise ConflictError('Appeal already decided.')
    validators.validate_appeal_outcome(outcome)
    appeal.status='DECIDED'; appeal.outcome=outcome; appeal.reviewed_by_user_id=actor.user_id; appeal.review_note=note; appeal.reviewed_at=timezone.now(); appeal.save()
    app=appeal.application
    app.status={'UPHELD':'REJECTION_UPHELD','REVERSED':'DECISION_MODIFIED','REMANDED':'REMANDED_FOR_AMENDMENT'}[outcome]; app.save(update_fields=['status','updated_at'])
    audit(actor,app,'APPEAL_DECIDED','Appeal',appeal.pk,new={'outcome':outcome,'application_status':app.status})
    return appeal

@transaction.atomic
def revise(actor, app, data):
    require(actor,'pms.application.revise')
    if app.applicant_user_id!=actor.user_id: raise PermissionDeniedError('Only applicant may revise.')
    if app.status not in ('NEEDS_REVISION','REJECTED'): raise ConflictError('Application is not awaiting revision.')
    if app.resubmission_deadline and timezone.localdate()>app.resubmission_deadline: raise ConflictError('The 60-day resubmission period has expired.')
    fields={k:data[k] for k in ('title','abstract','detailed_description','claims') if k in data}
    if not fields: raise ConflictError('At least one application field must be revised.')
    candidate={k:getattr(app,k) for k in ('title','abstract','detailed_description','claims')}
    candidate.update(fields)
    inventors=[{'full_name':i.full_name,'email':i.email,'ownership_percentage':i.ownership_share} for i in app.inventors.all()]
    validators.validate_submission_complete(candidate,inventors)
    for k,v in fields.items(): setattr(app,k,v)
    app.status='NEEDS_REVISION'; app.save(update_fields=[*fields,'status','updated_at'])
    audit(actor,app,'APPLICATION_REVISED','PatentApplication',app.pk,new={'revision':app.revision_number,'fields':sorted(fields)})
    return app

@transaction.atomic
def maintenance_decision(actor, event, decision, notes=''):
    require(actor,'pms.maintenance.manage')
    if event.application.status!='GRANTED': raise ConflictError('Maintenance is only available for granted patents.')
    if event.renewal_decision!='PENDING': raise ConflictError('Renewal decision already recorded.')
    event.renewal_decision='RENEW' if decision=='RENEW' else 'DO_NOT_RENEW'; event.decision_by_user_id=actor.user_id; event.decision_at=timezone.now(); event.notes=notes; event.save()
    audit(actor,event.application,'MAINTENANCE_DECISION','MaintenanceEvent',event.pk,new={'decision':event.renewal_decision,'notes':notes})
    return event

@transaction.atomic
def maintenance_completion(actor,event,reference):
    require(actor,'pms.maintenance.manage')
    if event.renewal_decision!='RENEW': raise ConflictError('Renewal must be approved before completion is recorded.')
    if not reference.strip(): raise ConflictError('Maintenance completion reference is required.')
    event.completion_reference=reference;event.completed_at=timezone.now();event.save()
    audit(actor,event.application,'MAINTENANCE_COMPLETED','MaintenanceEvent',event.pk,new={'reference':reference})
    return event
