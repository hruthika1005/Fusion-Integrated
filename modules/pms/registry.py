MODULE = {
    "code": "pms", "label": "Patent Management", "icon": "FaFileContract",
    "base_path": "/pms", "nav_section": "Research & Innovation", "sort_order": 40,
    "status": "active",
}
PERMISSIONS = [
    ("pms.application.submit", "Submit patent applications"),
    ("pms.application.view_self", "View own patent applications"),
    ("pms.application.view", "View PMS applications in assigned scope"),
    ("pms.application.assign_director", "Assign applications to directors"),
    ("pms.application.review", "Review and decide applications"),
    ("pms.application.revise", "Revise and resubmit applications"),
    ("pms.attorney.manage", "Manage attorney panel and assignments"),
    ("pms.attorney.respond", "Accept or decline attorney assignments"),
    ("pms.legal.assess", "Conduct legal and patentability assessment"),
    ("pms.budget.review", "Review and decide patent budgets"),
    ("pms.filing.manage", "Record patent filings"),
    ("pms.office_action.manage", "Manage office actions and responses"),
    ("pms.maintenance.manage", "Manage post-grant maintenance"),
    ("pms.license.manage", "Manage licensing and technology transfer"),
    ("pms.appeal.review", "Review patent appeals"),
    ("pms.report.view", "View PMS reports"),
    ("pms.audit.view", "View PMS audit trail"),
    ]
NAV_ITEMS = [
    {"code":"pms.my_applications","label":"My Patent Applications","icon":"FaFileAlt","to":"/pms/my-applications","required_permission":"pms.application.view_self","sort_order":10},
    {"code":"pms.applications","label":"Application Queue","icon":"FaInbox","to":"/pms/applications","required_permission":"pms.application.view","sort_order":20},
    {"code":"pms.attorneys","label":"Attorney Panel","icon":"FaUserTie","to":"/pms/attorneys","required_permission":"pms.attorney.manage","sort_order":30},
    {"code":"pms.reports","label":"Reports","icon":"FaChartBar","to":"/pms/reports","required_permission":"pms.report.view","sort_order":40},
]

ROLE_GRANTS = {
    "applicant": ["pms.application.submit", "pms.application.view_self", "pms.application.revise"],
    "student": ["pms.application.submit", "pms.application.view_self", "pms.application.revise"],
    "director": ["pms.application.view", "pms.application.review", "pms.budget.review", "pms.maintenance.manage", "pms.report.view"],
    "pcc_admin": ["pms.application.view", "pms.application.assign_director", "pms.attorney.manage", "pms.report.view", "pms.audit.view", "pms.license.manage"],
    "pcc_admin_role": ["pms.application.view", "pms.application.assign_director", "pms.attorney.manage", "pms.report.view", "pms.audit.view", "pms.license.manage"],
    "attorney": ["pms.application.view", "pms.attorney.respond", "pms.legal.assess", "pms.filing.manage", "pms.office_action.manage", "pms.maintenance.manage", "pms.report.view"],
}
