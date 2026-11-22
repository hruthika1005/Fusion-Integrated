from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView
from fusion_auth.permissions import HasModuleGrant,HasPermission
from core.api.exceptions import NotFoundError,PermissionDeniedError,ConflictError
from modules.pms.models import PatentApplication,Inventor
from modules.pms.services import workflow as w
class InventorConsent(APIView):
    permission_classes=[HasModuleGrant('pms'),HasPermission('pms.application.submit')]
    def post(self,request,pk,inv_id):
        app=w.visible_applications(request.principal).filter(pk=pk).first()
        if not app:raise NotFoundError('Patent application not found.')
        inv=Inventor.objects.filter(application=app,pk=inv_id).first()
        if not inv:raise NotFoundError('Inventor not found.')
        if inv.user_id != request.principal.user_id:raise PermissionDeniedError('Only the inventor may record their own consent.')
        consent=request.data.get('consent_status')
        if consent not in ('SIGNED','DECLINED'):raise ConflictError('consent_status must be SIGNED or DECLINED.')
        inv.consent_status=consent;inv.agreement_signed_at=timezone.now() if consent=='SIGNED' else None
        inv.signature_reference=str(request.data.get('signature_reference',''))[:255];inv.save()
        w.audit(request.principal,app,'INVENTOR_CONSENT_UPDATED','Inventor',inv.pk,new={'consent_status':consent})
        return Response({'id':inv.pk,'consent_status':inv.consent_status,'agreement_signed_at':inv.agreement_signed_at})
