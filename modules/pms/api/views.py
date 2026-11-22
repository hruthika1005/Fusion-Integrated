from django.http import FileResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from fusion_auth.permissions import HasModuleGrant, HasPermission
from core.api.exceptions import NotFoundError, ConflictError, PermissionDeniedError
from modules.pms import models as m
from modules.pms.api import serializers as s
from modules.pms.services import workflow as w
from modules.pms.services.domain_errors import translate
from modules.pms.services import documents as docs

MODULE=HasModuleGrant('pms')
def actor(request):return request.principal

def scoped(app_id, principal):
    app=w.visible_applications(principal).filter(pk=app_id).first()
    if app is None:raise NotFoundError('Patent application not found.')
    return app

class ApplicationListCreate(APIView):
    permission_classes=[MODULE]
    def get(self,request):
        qs=w.visible_applications(actor(request)).order_by('-created_at')
        return Response({'results':s.ApplicationSerializer(qs[:250],many=True).data})
    def post(self,request):
        permission=HasPermission('pms.application.submit')
        if not permission.has_permission(request,self):return Response({'detail':'Permission denied.'},status=403)
        payload=s.ApplicationCreate(data=request.data);payload.is_valid(raise_exception=True)
        app=translate(w.create_application)(actor(request),payload.validated_data)
        return Response(s.ApplicationSerializer(app).data,status=201)

class MyApplications(APIView):
    permission_classes=[MODULE,HasPermission('pms.application.view_self')]
    def get(self,request):
        qs=m.PatentApplication.objects.filter(applicant_user_id=actor(request).user_id).order_by('-created_at')
        return Response({'results':s.ApplicationSerializer(qs,many=True).data})

class ApplicationDetail(APIView):
    permission_classes=[MODULE]
    def get(self,request,pk):return Response(s.ApplicationSerializer(scoped(pk,actor(request))).data)

class SubmitApplication(APIView):
    permission_classes=[MODULE,HasPermission('pms.application.submit')]
    def post(self,request,pk):
        app=scoped(pk,actor(request));app=translate(w.submit)(actor(request),app)
        return Response(s.ApplicationSerializer(app).data)

class AssignDirector(APIView):
    permission_classes=[MODULE,HasPermission('pms.application.assign_director')]
    def post(self,request,pk):
        payload=s.AssignDirectorInput(data=request.data);payload.is_valid(raise_exception=True)
        app=translate(w.assign_director)(actor(request),scoped(pk,actor(request)),payload.validated_data['director_user_id'])
        return Response(s.ApplicationSerializer(app).data)

class DirectorReview(APIView):
    permission_classes=[MODULE,HasPermission('pms.application.review')]
    def post(self,request,pk):
        payload=s.ReviewInput(data=request.data);payload.is_valid(raise_exception=True)
        app=translate(w.review)(actor(request),scoped(pk,actor(request)),**payload.validated_data)
        return Response(s.ApplicationSerializer(app).data)

class AttorneyPanel(APIView):
    permission_classes=[MODULE,HasPermission('pms.attorney.manage')]
    def get(self,request):return Response({'results':list(m.AttorneyPanelMember.objects.order_by('full_name').values())})
    def post(self,request):
        payload=s.AttorneyPanelInput(data=request.data);payload.is_valid(raise_exception=True)
        obj,created=m.AttorneyPanelMember.objects.update_or_create(user_id=payload.validated_data['user_id'],defaults=payload.validated_data)
        return Response({'attorney':{k:getattr(obj,k) for k in ['id','user_id','full_name','email','expertise','approved','workload'] }},status=201 if created else 200)

class AssignAttorney(APIView):
    permission_classes=[MODULE,HasPermission('pms.attorney.manage')]
    def post(self,request,pk):
        payload=s.AttorneyInput(data=request.data);payload.is_valid(raise_exception=True)
        app=translate(w.assign_attorney)(actor(request),scoped(pk,actor(request)),payload.validated_data['attorney_user_id'])
        return Response(s.ApplicationSerializer(app).data)

class AttorneyAssignments(APIView):
    permission_classes=[MODULE,HasPermission('pms.attorney.respond')]
    def get(self,request):
        rows=m.AttorneyAssignment.objects.filter(attorney_user_id=actor(request).user_id).order_by('-created_at')
        return Response({'results':list(rows.values())})
    def post(self,request,pk):
        payload=s.AttorneyResponseInput(data=request.data);payload.is_valid(raise_exception=True)
        assignment=m.AttorneyAssignment.objects.filter(pk=pk,attorney_user_id=actor(request).user_id).first()
        if not assignment:raise NotFoundError('Assignment not found.')
        assignment=translate(w.attorney_response)(actor(request),assignment,**payload.validated_data)
        return Response({'assignment':s.AttorneyAssignmentSerializer(assignment).data})

class BudgetListCreate(APIView):
    permission_classes=[MODULE,HasPermission('pms.budget.review')]
    def get(self,request,pk):
        app=scoped(pk,actor(request));return Response({'results':list(app.budgets.values())})
    def post(self,request,pk):
        payload=s.BudgetInput(data=request.data);payload.is_valid(raise_exception=True)
        obj=translate(w.request_budget)(actor(request),scoped(pk,actor(request)),payload.validated_data)
        return Response({'budget':{**{k:getattr(obj,k) for k in ['id','status','currency','justification']},'total':str(obj.total)}},status=201)

class BudgetDecision(APIView):
    permission_classes=[MODULE,HasPermission('pms.budget.review')]
    def post(self,request,pk):
        payload=s.BudgetDecisionInput(data=request.data);payload.is_valid(raise_exception=True)
        obj=m.BudgetRequest.objects.filter(pk=pk).first()
        if not obj:raise NotFoundError('Budget request not found.')
        scoped(obj.application_id,actor(request))
        obj=translate(w.budget_decision)(actor(request),obj,**payload.validated_data)
        return Response({'id':obj.pk,'status':obj.status,'total':str(obj.total)})

class LegalOpinion(APIView):
    permission_classes=[MODULE,HasPermission('pms.legal.assess')]
    def get(self,request,pk):return Response({'results':list(scoped(pk,actor(request)).legal_opinions.values())})
    def post(self,request,pk):
        payload=s.LegalOpinionInput(data=request.data);payload.is_valid(raise_exception=True)
        obj=translate(w.legal_opinion)(actor(request),scoped(pk,actor(request)),payload.validated_data)
        return Response({'opinion':{k:getattr(obj,k) for k in ['id','recommendation','version','created_at']}},status=201)

class Filing(APIView):
    permission_classes=[MODULE,HasPermission('pms.filing.manage')]
    def post(self,request,pk):
        payload=s.FilingInput(data=request.data);payload.is_valid(raise_exception=True)
        obj=translate(w.record_filing)(actor(request),scoped(pk,actor(request)),payload.validated_data)
        return Response({'filing':{k:getattr(obj,k) for k in ['id','patent_office','external_filing_id','filing_date','filing_type']}},status=201)

class OfficeActions(APIView):
    permission_classes=[MODULE,HasPermission('pms.office_action.manage')]
    def get(self,request,pk):return Response({'results':list(scoped(pk,actor(request)).office_actions.values())})
    def post(self,request,pk):
        payload=s.OfficeActionInput(data=request.data);payload.is_valid(raise_exception=True)
        obj=translate(w.record_office_action)(actor(request),scoped(pk,actor(request)),payload.validated_data)
        return Response({'office_action':{k:getattr(obj,k) for k in ['id','patent_office_reference','received_date','response_deadline','status']}},status=201)

class OfficeActionResponse(APIView):
    permission_classes=[MODULE,HasPermission('pms.office_action.manage')]
    def post(self,request,pk):
        payload=s.OfficeResponseInput(data=request.data);payload.is_valid(raise_exception=True)
        obj=m.OfficeAction.objects.filter(pk=pk).first()
        if not obj:raise NotFoundError('Office action not found.')
        scoped(obj.application_id,actor(request))
        obj=translate(w.submit_office_response)(actor(request),obj,payload.validated_data['response_text'])
        return Response({'id':obj.pk,'status':obj.status,'submitted_at':obj.submitted_at})

class Appeals(APIView):
    permission_classes=[MODULE]
    def post(self,request,pk):
        if not HasPermission('pms.application.submit').has_permission(request,self):return Response({'detail':'Permission denied'},status=403)
        payload=s.AppealInput(data=request.data);payload.is_valid(raise_exception=True)
        obj=translate(w.create_appeal)(actor(request),scoped(pk,actor(request)),payload.validated_data['grounds'])
        return Response({'id':obj.pk,'status':obj.status},status=201)

class AppealDecision(APIView):
    permission_classes=[MODULE,HasPermission('pms.appeal.review')]
    def post(self,request,pk):
        payload=s.AppealDecisionInput(data=request.data);payload.is_valid(raise_exception=True)
        obj=m.Appeal.objects.filter(pk=pk).first()
        if not obj:raise NotFoundError('Appeal not found.')
        scoped(obj.application_id,actor(request))
        obj=translate(w.decide_appeal)(actor(request),obj,**payload.validated_data)
        return Response({'id':obj.pk,'status':obj.status,'outcome':obj.outcome})

class PriorArt(APIView):
    permission_classes=[MODULE]
    def get(self,request,pk):return Response({'results':list(scoped(pk,actor(request)).prior_art.values())})
    def post(self,request,pk):
        app=scoped(pk,actor(request));payload=s.PriorArtInput(data=request.data);payload.is_valid(raise_exception=True)
        if not (app.applicant_user_id==actor(request).user_id or app.assigned_attorney_id==actor(request).user_id or HasPermission('pms.application.view').has_permission(request,self)):
            return Response({'detail':'Permission denied.'},status=403)
        obj=m.PriorArtReference.objects.create(application=app,added_by_user_id=actor(request).user_id,**payload.validated_data)
        w.audit(actor(request),app,'PRIOR_ART_ADDED','PriorArtReference',obj.pk,new={'title':obj.title})
        return Response({'id':obj.pk,'title':obj.title,'reference_url':obj.reference_url},status=201)

class LicenseRequests(APIView):
    permission_classes=[MODULE]
    def post(self,request,pk):
        app=scoped(pk,actor(request));payload=s.LicenseInput(data=request.data);payload.is_valid(raise_exception=True)
        if app.applicant_user_id!=actor(request).user_id:return Response({'detail':'Permission denied.'},status=403)
        obj=m.LicenseRequest.objects.create(application=app,requested_by_user_id=actor(request).user_id,**payload.validated_data)
        w.audit(actor(request),app,'LICENSE_REQUEST_SUBMITTED','LicenseRequest',obj.pk,new={'status':obj.status})
        return Response({'id':obj.pk,'status':obj.status},status=201)
    def get(self,request,pk):return Response({'results':list(scoped(pk,actor(request)).license_requests.values())})

class LicenseDecision(APIView):
    permission_classes=[MODULE,HasPermission('pms.license.manage')]
    def post(self,request,pk):
        payload=s.LicenseDecisionInput(data=request.data);payload.is_valid(raise_exception=True)
        obj=m.LicenseRequest.objects.filter(pk=pk).first()
        if not obj:raise NotFoundError('License request not found.')
        scoped(obj.application_id,actor(request))
        obj.status=payload.validated_data['status'];obj.reviewed_by_user_id=actor(request).user_id;obj.review_note=payload.validated_data.get('note','');obj.reviewed_at=timezone.now();obj.save()
        w.audit(actor(request),obj.application,'LICENSE_REQUEST_REVIEWED','LicenseRequest',obj.pk,new={'status':obj.status})
        return Response({'id':obj.pk,'status':obj.status})

class AuditTrail(APIView):
    permission_classes=[MODULE,HasPermission('pms.audit.view')]
    def get(self,request,pk):return Response({'results':s.AuditSerializer(scoped(pk,actor(request)).audit_events.all()[:500],many=True).data})

class Reports(APIView):
    permission_classes=[MODULE,HasPermission('pms.report.view')]
    def get(self,request):
        qs=w.visible_applications(actor(request))
        return Response({'total':qs.count(),'by_status':{status:qs.filter(status=status).count() for status,_ in m.PatentApplication.STATUS},'budgets_pending':m.BudgetRequest.objects.filter(application__in=qs,status='PENDING').count(),'deadlines_open':m.Deadline.objects.filter(application__in=qs,status='OPEN').count()})

class UploadDocument(APIView):
    permission_classes=[MODULE]
    def post(self,request,pk):
        app=scoped(pk,actor(request));uploaded=request.FILES.get('file');category=request.data.get('category','SUPPORTING')
        obj=docs.attach(actor=actor(request),application=app,uploaded_file=uploaded,category=category,sensitivity=request.data.get('sensitivity','CONFIDENTIAL'))
        w.audit(actor(request),app,'DOCUMENT_UPLOADED','PmsDocument',obj.pk,new={'category':category,'scan_status':obj.scan_status})
        return Response({'id':obj.pk,'filename':obj.original_filename,'version':obj.version,'scan_status':obj.scan_status},status=201)

class Documents(APIView):
    permission_classes=[MODULE]
    def get(self,request,pk):
        app=scoped(pk,actor(request));return Response({'results':list(app.documents.values('id','category','sensitivity','original_filename','version','is_current','scan_status','created_at'))})

class DocumentDownload(APIView):
    permission_classes=[MODULE]
    def get(self,request,pk):
        doc=m.PmsDocument.objects.filter(pk=pk).first()
        if not doc:raise NotFoundError('Document not found.')
        docs.download_allowed(actor(request),doc)
        return FileResponse(doc.file.open('rb'),as_attachment=True,filename=doc.original_filename)

class DeadlineList(APIView):
    permission_classes=[MODULE,HasPermission('pms.report.view')]
    def get(self,request):
        qs=m.Deadline.objects.filter(status='OPEN').order_by('due_date')
        if not HasPermission('pms.application.view').has_permission(request,self):qs=qs.filter(responsible_user_id=actor(request).user_id)
        return Response({'results':s.DeadlineSerializer(qs[:500],many=True).data})

class Revision(APIView):
    permission_classes=[MODULE,HasPermission('pms.application.revise')]
    def post(self,request,pk):
        payload=s.RevisionInput(data=request.data);payload.is_valid(raise_exception=True)
        app=translate(w.revise)(actor(request),scoped(pk,actor(request)),payload.validated_data)
        return Response(s.ApplicationSerializer(app).data)

class Maintenance(APIView):
    permission_classes=[MODULE,HasPermission('pms.maintenance.manage')]
    def get(self,request,pk):return Response({'results':list(scoped(pk,actor(request)).maintenance_events.values())})
    def post(self,request,pk):
        payload=s.MaintenanceCreateInput(data=request.data);payload.is_valid(raise_exception=True)
        app=scoped(pk,actor(request))
        if app.status!='GRANTED':raise ConflictError('Maintenance schedules only apply to granted patents.')
        obj=m.MaintenanceEvent.objects.create(application=app,**payload.validated_data)
        w.audit(actor(request),app,'MAINTENANCE_SCHEDULE_CREATED','MaintenanceEvent',obj.pk,new={'due_date':str(obj.due_date),'jurisdiction':obj.jurisdiction})
        return Response({'id':obj.pk,'due_date':obj.due_date,'renewal_decision':obj.renewal_decision},status=201)
    def patch(self,request,pk):
        payload=s.MaintenanceDecisionInput(data=request.data);payload.is_valid(raise_exception=True)
        obj=m.MaintenanceEvent.objects.filter(pk=pk).first()
        if not obj:raise NotFoundError('Maintenance event not found.')
        obj=translate(w.maintenance_decision)(actor(request),obj,**payload.validated_data)
        return Response({'id':obj.pk,'renewal_decision':obj.renewal_decision})

class MaintenanceCompletion(APIView):
    permission_classes=[MODULE,HasPermission('pms.maintenance.manage')]
    def post(self,request,pk):
        payload=s.MaintenanceCompletionInput(data=request.data);payload.is_valid(raise_exception=True)
        obj=m.MaintenanceEvent.objects.filter(pk=pk).first()
        if not obj:raise NotFoundError('Maintenance event not found.')
        obj=translate(w.maintenance_completion)(actor(request),obj,payload.validated_data['completion_reference'])
        return Response({'id':obj.pk,'completed_at':obj.completed_at,'completion_reference':obj.completion_reference})

class MaintenanceDecision(APIView):
    permission_classes=[MODULE,HasPermission('pms.maintenance.manage')]
    def post(self,request,pk):
        payload=s.MaintenanceDecisionInput(data=request.data);payload.is_valid(raise_exception=True)
        obj=m.MaintenanceEvent.objects.filter(pk=pk).first()
        if not obj:raise NotFoundError('Maintenance event not found.')
        scoped(obj.application_id,actor(request))
        obj=translate(w.maintenance_decision)(actor(request),obj,**payload.validated_data)
        return Response({'id':obj.pk,'renewal_decision':obj.renewal_decision})

class ApplicantOfficeActionApproval(APIView):
    permission_classes=[MODULE,HasPermission('pms.application.view_self')]
    def post(self,request,pk):
        obj=m.OfficeAction.objects.filter(pk=pk).first()
        if not obj:raise NotFoundError('Office action not found.')
        if obj.application.applicant_user_id!=actor(request).user_id:raise PermissionDeniedError('Only applicant may approve this response.')
        if obj.status not in ('REVIEW','APPLICANT_APPROVAL','RESPONSE_DRAFT'):raise ConflictError('Office action is not awaiting applicant approval.')
        obj.applicant_approved_at=timezone.now();obj.status='APPLICANT_APPROVED';obj.save(update_fields=['applicant_approved_at','status','updated_at'])
        w.audit(actor(request),obj.application,'OFFICE_ACTION_RESPONSE_APPROVED','OfficeAction',obj.pk,new={'status':obj.status})
        return Response({'id':obj.pk,'status':obj.status,'approved_at':obj.applicant_approved_at})
