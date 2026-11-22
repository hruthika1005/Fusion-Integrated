from django.core.management.base import BaseCommand
from django.utils import timezone
from modules.pms.models import PatentApplication
from modules.pms.services.workflow import audit

class Command(BaseCommand):
    help='Expire PMS applications whose 60-day revision/resubmission deadline has passed.'
    def handle(self,*args,**options):
        today=timezone.localdate()
        qs=PatentApplication.objects.filter(status__in=['NEEDS_REVISION','REJECTED'],resubmission_deadline__lt=today)
        count=0
        for app in qs.iterator():
            old=app.status;app.status='EXPIRED';app.save(update_fields=['status','updated_at'])
            audit(None,app,'RESUBMISSION_EXPIRED','PatentApplication',app.pk,old={'status':old},new={'status':'EXPIRED'},metadata={'deadline':str(app.resubmission_deadline)})
            count+=1
        self.stdout.write(self.style.SUCCESS(f'Expired {count} PMS application(s).'))
