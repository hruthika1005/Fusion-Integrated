from rest_framework.views import APIView
from rest_framework.response import Response
from fusion_auth.permissions import HasModuleGrant,HasPermission
from core.api.exceptions import ConflictError,PermissionDeniedError,NotFoundError
from modules.pms.models import PatentApplication
from modules.pms.domain.validators import validate_reason
from modules.pms.services import workflow as w
from modules.pms.services.domain_errors import translate
from modules.pms.services.domain_errors import translate
class Withdrawal(APIView):
    permission_classes=[HasModuleGrant('pms'),HasPermission('pms.application.submit')]
    def post(self,request,pk):
        app=w.visible_applications(request.principal).filter(pk=pk).first()
        if not app:raise NotFoundError('Patent application not found.')
        if app.applicant_user_id!=request.principal.user_id:raise PermissionDeniedError('Only applicant may withdraw.')
        if app.status in ('FILED','GRANTED','CLOSED','WITHDRAWN'):raise ConflictError('Withdrawal is not allowed at this stage.')
        reason=translate(validate_reason)(request.data.get('reason',''))
        old=app.status;app.status='WITHDRAWN';app.withdrawal_reason=reason;app.save(update_fields=['status','withdrawal_reason','updated_at'])
        w.audit(request.principal,app,'APPLICATION_WITHDRAWN','PatentApplication',app.pk,old={'status':old},new={'status':'WITHDRAWN','reason':reason})
        return Response({'application_id':app.pk,'status':app.status})
