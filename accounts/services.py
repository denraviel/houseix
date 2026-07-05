from django.urls import NoReverseMatch, reverse

from .models import JobPosition


class NavigationService:
    MODULE_DASHBOARD = 'dashboard'
    MODULE_STAFF_MANAGEMENT = 'staff_management'
    MODULE_PRODUCTS = 'products'
    MODULE_INVENTORY = 'inventory'
    MODULE_SALES = 'sales'
    MODULE_CUSTOMERS = 'customers'
    MODULE_ROOMS = 'rooms'
    MODULE_STAYS = 'stays'
    MODULE_INVOICES = 'invoices'
    MODULE_EXPENSES = 'expenses'
    MODULE_TASKS = 'tasks'
    MODULE_MY_TASKS = 'my_tasks'
    MODULE_MAINTENANCE = 'maintenance'
    MODULE_INSPECTIONS = 'inspections'
    MODULE_PERFORMANCE = 'performance'
    MODULE_REPORTS = 'reports'

    MODULE_MENU_ORDER = [
        MODULE_DASHBOARD,
        MODULE_STAFF_MANAGEMENT,
        MODULE_PRODUCTS,
        MODULE_INVENTORY,
        MODULE_SALES,
        MODULE_CUSTOMERS,
        MODULE_ROOMS,
        MODULE_STAYS,
        MODULE_INVOICES,
        MODULE_EXPENSES,
        MODULE_TASKS,
        MODULE_MY_TASKS,
        MODULE_MAINTENANCE,
        MODULE_INSPECTIONS,
        MODULE_PERFORMANCE,
        MODULE_REPORTS,
    ]

    MODULE_DEFINITIONS = {
        MODULE_DASHBOARD: {'label': 'Dashboard'},
        MODULE_STAFF_MANAGEMENT: {'label': 'Staff Management', 'url_name': 'staff_list'},
        MODULE_PRODUCTS: {'label': 'Products', 'url_name': 'product_list'},
        MODULE_INVENTORY: {'label': 'Inventory', 'url_name': 'inventory_list'},
        MODULE_SALES: {'label': 'Sales', 'url_name': 'sales_list'},
        MODULE_CUSTOMERS: {'label': 'Customers', 'url_name': 'customer_list'},
        MODULE_ROOMS: {'label': 'Rooms', 'url_name': 'room_list'},
        MODULE_STAYS: {'label': 'Guest Stays', 'url_name': 'stay_list'},
        MODULE_INVOICES: {'label': 'Invoices', 'url_name': 'invoice_list'},
        MODULE_EXPENSES: {'label': 'Expenses', 'url_name': 'expense_dashboard'},
        MODULE_TASKS: {'label': 'Tasks', 'url_name': 'task_list'},
        MODULE_MY_TASKS: {'label': 'My Tasks', 'url_name': 'my_tasks'},
        MODULE_MAINTENANCE: {'label': 'Maintenance', 'url_name': 'maintenance_dashboard'},
        MODULE_INSPECTIONS: {'label': 'Inspections', 'url_name': 'inspection_list'},
        MODULE_PERFORMANCE: {'label': 'Performance', 'url_name': 'my_performance'},
        MODULE_REPORTS: {'label': 'Reports', 'url_name': 'reports_dashboard'},
    }

    URL_NAME_TO_MODULE = {
        'admin_dashboard': MODULE_DASHBOARD,
        'employee_dashboard': MODULE_DASHBOARD,
        'staff_list': MODULE_STAFF_MANAGEMENT,
        'staff_create': MODULE_STAFF_MANAGEMENT,
        'staff_edit': MODULE_STAFF_MANAGEMENT,
        'staff_delete': MODULE_STAFF_MANAGEMENT,
        'toggle_staff_active': MODULE_STAFF_MANAGEMENT,
        'product_list': MODULE_PRODUCTS,
        'product_create': MODULE_PRODUCTS,
        'product_update': MODULE_PRODUCTS,
        'product_toggle_active': MODULE_PRODUCTS,
        'product_delete': MODULE_PRODUCTS,
        'inventory_list': MODULE_INVENTORY,
        'inventory_item_create': MODULE_INVENTORY,
        'inventory_item_edit': MODULE_INVENTORY,
        'inventory_item_delete': MODULE_INVENTORY,
        'add_stock': MODULE_INVENTORY,
        'stock_movement_create': MODULE_INVENTORY,
        'sales_list': MODULE_SALES,
        'sale_create': MODULE_SALES,
        'sale_delete': MODULE_SALES,
        'customer_list': MODULE_CUSTOMERS,
        'customer_create': MODULE_CUSTOMERS,
        'customer_detail': MODULE_CUSTOMERS,
        'customer_update': MODULE_CUSTOMERS,
        'customer_delete': MODULE_CUSTOMERS,
        'room_list': MODULE_ROOMS,
        'room_create': MODULE_ROOMS,
        'room_update': MODULE_ROOMS,
        'room_delete': MODULE_ROOMS,
        'room_change_status': MODULE_ROOMS,
        'stay_list': MODULE_STAYS,
        'stay_create': MODULE_STAYS,
        'stay_detail': MODULE_STAYS,
        'stay_update': MODULE_STAYS,
        'stay_status_update': MODULE_STAYS,
        'invoice_list': MODULE_INVOICES,
        'invoice_create': MODULE_INVOICES,
        'invoice_history': MODULE_INVOICES,
        'invoice_generate': MODULE_INVOICES,
        'invoice_detail': MODULE_INVOICES,
        'invoice_update': MODULE_INVOICES,
        'invoice_payment': MODULE_INVOICES,
        'invoice_print': MODULE_INVOICES,
        'invoice_pdf': MODULE_INVOICES,
        'expense_dashboard': MODULE_EXPENSES,
        'expense_list': MODULE_EXPENSES,
        'expense_create': MODULE_EXPENSES,
        'expense_detail': MODULE_EXPENSES,
        'expense_update': MODULE_EXPENSES,
        'expense_delete': MODULE_EXPENSES,
        'expense_approval': MODULE_EXPENSES,
        'expense_category_list': MODULE_EXPENSES,
        'expense_category_create': MODULE_EXPENSES,
        'vendor_list': MODULE_EXPENSES,
        'vendor_create': MODULE_EXPENSES,
        'recurring_expense_list': MODULE_EXPENSES,
        'recurring_expense_create': MODULE_EXPENSES,
        'recurring_expense_generate': MODULE_EXPENSES,
        'fuel_log_list': MODULE_EXPENSES,
        'fuel_log_create': MODULE_EXPENSES,
        'task_list': MODULE_TASKS,
        'task_create': MODULE_TASKS,
        'task_update': MODULE_TASKS,
        'task_delete': MODULE_TASKS,
        'my_tasks': MODULE_MY_TASKS,
        'staff_task_start': MODULE_MY_TASKS,
        'staff_task_complete': MODULE_MY_TASKS,
        'staff_task_update': MODULE_MY_TASKS,
        'maintenance_dashboard': MODULE_MAINTENANCE,
        'maintenance_issue_list': MODULE_MAINTENANCE,
        'maintenance_issue_create': MODULE_MAINTENANCE,
        'maintenance_issue_detail': MODULE_MAINTENANCE,
        'maintenance_issue_update': MODULE_MAINTENANCE,
        'maintenance_issue_assign': MODULE_MAINTENANCE,
        'maintenance_issue_verify': MODULE_MAINTENANCE,
        'maintenance_issue_escalate': MODULE_MAINTENANCE,
        'maintenance_issue_record_expense': MODULE_MAINTENANCE,
        'maintenance_category_list': MODULE_MAINTENANCE,
        'maintenance_category_create': MODULE_MAINTENANCE,
        'maintenance_activity_list': MODULE_MAINTENANCE,
        'inspection_list': MODULE_INSPECTIONS,
        'inspection_history': MODULE_INSPECTIONS,
        'inspection_detail': MODULE_INSPECTIONS,
        'inspection_update': MODULE_INSPECTIONS,
        'inspection_submit': MODULE_INSPECTIONS,
        'inspection_create': MODULE_INSPECTIONS,
        'my_performance': MODULE_PERFORMANCE,
        'performance_dashboard': MODULE_PERFORMANCE,
        'performance_reports': MODULE_PERFORMANCE,
        'staff_performance_detail': MODULE_PERFORMANCE,
        'performance_rating_create': MODULE_PERFORMANCE,
        'reports_dashboard': MODULE_REPORTS,
        'sales_report': MODULE_REPORTS,
        'inventory_report': MODULE_REPORTS,
        'product_performance_report': MODULE_REPORTS,
        'staff_performance_report': MODULE_REPORTS,
        'activity_report': MODULE_REPORTS,
    }

    STAFF_ROLE_FALLBACK_MODULES = {
        MODULE_DASHBOARD,
        MODULE_SALES,
        MODULE_INVENTORY,
        MODULE_CUSTOMERS,
        MODULE_ROOMS,
        MODULE_STAYS,
        MODULE_INVOICES,
        MODULE_EXPENSES,
        MODULE_MY_TASKS,
        MODULE_MAINTENANCE,
        MODULE_PERFORMANCE,
    }
    MANAGER_ROLE_FALLBACK_MODULES = set(MODULE_MENU_ORDER) - {MODULE_MY_TASKS}

    STAFF_DEPARTMENT_MODULES = {
        JobPosition.DEPARTMENT_FRONT_OFFICE: {MODULE_DASHBOARD, MODULE_STAYS, MODULE_CUSTOMERS, MODULE_ROOMS, MODULE_INVOICES, MODULE_MY_TASKS},
        JobPosition.DEPARTMENT_HOUSEKEEPING: {MODULE_DASHBOARD, MODULE_MY_TASKS, MODULE_MAINTENANCE, MODULE_PERFORMANCE},
        JobPosition.DEPARTMENT_MAINTENANCE: {MODULE_DASHBOARD, MODULE_MY_TASKS, MODULE_MAINTENANCE, MODULE_PERFORMANCE},
        JobPosition.DEPARTMENT_SECURITY: {MODULE_DASHBOARD, MODULE_MY_TASKS, MODULE_MAINTENANCE},
        JobPosition.DEPARTMENT_FOOD_BEVERAGE: {MODULE_DASHBOARD, MODULE_SALES, MODULE_INVENTORY, MODULE_MY_TASKS},
        JobPosition.DEPARTMENT_STORE: {MODULE_DASHBOARD, MODULE_INVENTORY, MODULE_PRODUCTS, MODULE_MY_TASKS},
        JobPosition.DEPARTMENT_FINANCE: {MODULE_DASHBOARD, MODULE_INVOICES, MODULE_EXPENSES, MODULE_REPORTS, MODULE_MY_TASKS},
        JobPosition.DEPARTMENT_SALES_MARKETING: {MODULE_DASHBOARD, MODULE_SALES, MODULE_CUSTOMERS, MODULE_REPORTS, MODULE_MY_TASKS},
        JobPosition.DEPARTMENT_DRIVER: {MODULE_DASHBOARD, MODULE_MY_TASKS},
        JobPosition.DEPARTMENT_GENERAL_STAFF: {MODULE_DASHBOARD, MODULE_MY_TASKS, MODULE_PERFORMANCE},
        JobPosition.DEPARTMENT_GENERAL_MANAGEMENT: STAFF_ROLE_FALLBACK_MODULES,
    }

    MANAGER_DEPARTMENT_MODULES = {
        JobPosition.DEPARTMENT_GENERAL_MANAGEMENT: set(MODULE_MENU_ORDER) - {MODULE_MY_TASKS},
        JobPosition.DEPARTMENT_FRONT_OFFICE: {MODULE_DASHBOARD, MODULE_CUSTOMERS, MODULE_ROOMS, MODULE_STAYS, MODULE_INVOICES, MODULE_TASKS, MODULE_REPORTS},
        JobPosition.DEPARTMENT_HOUSEKEEPING: {MODULE_DASHBOARD, MODULE_TASKS, MODULE_INSPECTIONS, MODULE_MAINTENANCE, MODULE_PERFORMANCE, MODULE_REPORTS},
        JobPosition.DEPARTMENT_MAINTENANCE: {MODULE_DASHBOARD, MODULE_TASKS, MODULE_MAINTENANCE, MODULE_PERFORMANCE, MODULE_REPORTS},
        JobPosition.DEPARTMENT_SECURITY: {MODULE_DASHBOARD, MODULE_TASKS, MODULE_MAINTENANCE, MODULE_REPORTS},
        JobPosition.DEPARTMENT_FOOD_BEVERAGE: {MODULE_DASHBOARD, MODULE_PRODUCTS, MODULE_INVENTORY, MODULE_SALES, MODULE_TASKS, MODULE_REPORTS},
        JobPosition.DEPARTMENT_STORE: {MODULE_DASHBOARD, MODULE_PRODUCTS, MODULE_INVENTORY, MODULE_TASKS, MODULE_REPORTS},
        JobPosition.DEPARTMENT_FINANCE: {MODULE_DASHBOARD, MODULE_INVOICES, MODULE_EXPENSES, MODULE_REPORTS, MODULE_TASKS},
        JobPosition.DEPARTMENT_SALES_MARKETING: {MODULE_DASHBOARD, MODULE_CUSTOMERS, MODULE_SALES, MODULE_REPORTS, MODULE_TASKS},
        JobPosition.DEPARTMENT_DRIVER: {MODULE_DASHBOARD, MODULE_TASKS},
        JobPosition.DEPARTMENT_GENERAL_STAFF: {MODULE_DASHBOARD, MODULE_TASKS, MODULE_REPORTS},
    }

    @staticmethod
    def _user_positions(user):
        if not getattr(user, 'is_authenticated', False):
            return []
        if hasattr(user, '_ordered_positions'):
            return user._ordered_positions()
        return list(user.positions.filter(is_active=True).order_by('department', 'name'))

    @classmethod
    def get_accessible_modules(cls, user):
        if not getattr(user, 'is_authenticated', False):
            return set()
        role = getattr(user, 'role', '')
        if role in ['owner', 'admin']:
            return set(cls.MODULE_MENU_ORDER)

        positions = cls._user_positions(user)
        if not positions:
            return cls.MANAGER_ROLE_FALLBACK_MODULES.copy() if role == 'manager' else cls.STAFF_ROLE_FALLBACK_MODULES.copy()

        if role == 'manager':
            modules = {cls.MODULE_DASHBOARD, cls.MODULE_TASKS}
            for position in positions:
                modules.update(cls.MANAGER_DEPARTMENT_MODULES.get(position.department, {cls.MODULE_DASHBOARD, cls.MODULE_TASKS}))
            return modules
        if role == 'staff':
            modules = {cls.MODULE_DASHBOARD, cls.MODULE_MY_TASKS}
            for position in positions:
                modules.update(cls.STAFF_DEPARTMENT_MODULES.get(position.department, {cls.MODULE_DASHBOARD, cls.MODULE_MY_TASKS}))
            return modules
        return set(cls.MODULE_MENU_ORDER)

    @classmethod
    def can_access_module(cls, user, module_code):
        return module_code in cls.get_accessible_modules(user)

    @classmethod
    def get_module_for_url_name(cls, url_name):
        return cls.URL_NAME_TO_MODULE.get(url_name)

    @classmethod
    def can_access_url_name(cls, user, url_name):
        module_code = cls.get_module_for_url_name(url_name)
        if not module_code:
            return True
        return cls.can_access_module(user, module_code)

    @staticmethod
    def get_dashboard_url_name(user):
        return 'admin_dashboard' if getattr(user, 'role', '') in ['owner', 'admin', 'manager'] else 'employee_dashboard'

    @staticmethod
    def get_performance_url_name(user):
        return 'my_performance' if getattr(user, 'role', '') == 'staff' else 'performance_reports'

    @classmethod
    def get_dashboard_title(cls, user):
        positions = cls._user_positions(user)
        if positions:
            if len(positions) == 1:
                return f'{positions[0].name} Dashboard'
            return 'Multi-Position Dashboard'
        role = getattr(user, 'get_role_display', None)
        return f'{role() if callable(role) else "User"} Dashboard'

    @classmethod
    def get_menu_items(cls, user):
        modules = cls.get_accessible_modules(user)
        items = []
        for module_code in cls.MODULE_MENU_ORDER:
            if module_code not in modules:
                continue
            definition = dict(cls.MODULE_DEFINITIONS[module_code])
            if module_code == cls.MODULE_DASHBOARD:
                url_name = cls.get_dashboard_url_name(user)
            elif module_code == cls.MODULE_PERFORMANCE:
                url_name = cls.get_performance_url_name(user)
            else:
                url_name = definition.get('url_name')
            if not url_name:
                continue
            try:
                url = reverse(url_name)
            except NoReverseMatch:
                continue
            items.append(
                {
                    'code': module_code,
                    'label': definition['label'],
                    'url_name': url_name,
                    'url': url,
                }
            )
        return items

    @classmethod
    def get_dashboard_widgets(cls, user):
        modules = cls.get_accessible_modules(user)
        widgets = []
        widget_map = {
            cls.MODULE_MY_TASKS: ('Assigned Tasks', 'Track and update your operational work.', 'my_tasks'),
            cls.MODULE_TASKS: ('Task Management', 'Assign and monitor department work.', 'task_list'),
            cls.MODULE_INSPECTIONS: ('Inspections', 'Review checklist audits and quality control.', 'inspection_list'),
            cls.MODULE_MAINTENANCE: ('Maintenance', 'View repair issues and status updates.', 'maintenance_dashboard'),
            cls.MODULE_SALES: ('Sales', 'Open the sales workflow for active operations.', 'sales_list'),
            cls.MODULE_INVENTORY: ('Inventory', 'Monitor stock and movements for your area.', 'inventory_list'),
            cls.MODULE_CUSTOMERS: ('Customers', 'Open guest and customer records.', 'customer_list'),
            cls.MODULE_ROOMS: ('Rooms', 'Review room inventory and availability.', 'room_list'),
            cls.MODULE_STAYS: ('Guest Stays', 'Handle reservations, check-in, and check-out.', 'stay_list'),
            cls.MODULE_INVOICES: ('Invoices', 'Access invoice history and billing workflows.', 'invoice_list'),
            cls.MODULE_EXPENSES: ('Expenses', 'Review operational costs and submissions.', 'expense_dashboard'),
            cls.MODULE_REPORTS: ('Reports', 'View management and analytical reports.', 'reports_dashboard'),
            cls.MODULE_PERFORMANCE: ('Performance', 'Open performance ratings and history.', 'my_performance' if getattr(user, 'role', '') == 'staff' else 'performance_reports'),
        }
        for module_code in cls.MODULE_MENU_ORDER:
            if module_code not in modules or module_code not in widget_map:
                continue
            title, subtitle, url_name = widget_map[module_code]
            try:
                url = reverse(url_name)
            except NoReverseMatch:
                continue
            widgets.append(
                {
                    'code': module_code,
                    'title': title,
                    'subtitle': subtitle,
                    'url_name': url_name,
                    'url': url,
                }
            )
        return widgets[:6]
