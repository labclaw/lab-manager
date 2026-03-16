"""SQLAdmin configuration — admin UI for all models."""

from __future__ import annotations

from sqladmin import Admin, ModelView

from lab_manager.models.vendor import Vendor
from lab_manager.models.product import Product
from lab_manager.models.staff import Staff
from lab_manager.models.location import StorageLocation
from lab_manager.models.order import Order, OrderItem
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.document import Document
from lab_manager.models.alert import Alert
from lab_manager.models.audit import AuditLog


class VendorAdmin(ModelView, model=Vendor):
    column_list = [Vendor.id, Vendor.name, Vendor.website, Vendor.created_at]
    column_searchable_list = [Vendor.name]


class ProductAdmin(ModelView, model=Product):
    column_list = [Product.id, Product.catalog_number, Product.name, Product.category]
    column_searchable_list = [Product.catalog_number, Product.name]


class StaffAdmin(ModelView, model=Staff):
    column_list = [Staff.id, Staff.name, Staff.email, Staff.role, Staff.is_active]


class LocationAdmin(ModelView, model=StorageLocation):
    column_list = [
        StorageLocation.id,
        StorageLocation.name,
        StorageLocation.room,
        StorageLocation.temperature,
    ]


class OrderAdmin(ModelView, model=Order):
    column_list = [
        Order.id,
        Order.po_number,
        Order.order_date,
        Order.status,
        Order.received_by,
    ]
    column_searchable_list = [Order.po_number, Order.delivery_number]


class OrderItemAdmin(ModelView, model=OrderItem):
    column_list = [
        OrderItem.id,
        OrderItem.catalog_number,
        OrderItem.description,
        OrderItem.lot_number,
        OrderItem.quantity,
    ]
    column_searchable_list = [OrderItem.catalog_number, OrderItem.lot_number]


class InventoryAdmin(ModelView, model=InventoryItem):
    column_list = [
        InventoryItem.id,
        InventoryItem.quantity_on_hand,
        InventoryItem.lot_number,
        InventoryItem.expiry_date,
        InventoryItem.status,
    ]


class DocumentAdmin(ModelView, model=Document):
    column_list = [
        Document.id,
        Document.file_name,
        Document.document_type,
        Document.vendor_name,
        Document.status,
    ]
    column_searchable_list = [Document.file_name, Document.vendor_name]


class AuditLogAdmin(ModelView, model=AuditLog):
    column_list = [
        AuditLog.id,
        AuditLog.table_name,
        AuditLog.action,
        AuditLog.changed_by,
        AuditLog.timestamp,
    ]


class AlertAdmin(ModelView, model=Alert):
    column_list = [
        Alert.id,
        Alert.alert_type,
        Alert.severity,
        Alert.entity_type,
        Alert.entity_id,
        Alert.is_acknowledged,
        Alert.is_resolved,
        Alert.created_at,
    ]
    column_searchable_list = [Alert.alert_type, Alert.severity]


def _make_auth_backend():
    import hmac

    from sqladmin.authentication import AuthenticationBackend

    class AdminAuthBackend(AuthenticationBackend):
        async def login(self, request) -> bool:
            from lab_manager.config import get_settings

            settings = get_settings()
            if not settings.auth_enabled:
                request.session["authenticated"] = True
                return True
            form = await request.form()
            username = form.get("username", "")
            password = form.get("password", "")
            if (
                settings.api_key
                and hmac.compare_digest(username, "admin")
                and hmac.compare_digest(password, settings.api_key)
            ):
                request.session["authenticated"] = True
                return True
            return False

        async def logout(self, request) -> bool:
            request.session.clear()
            return True

        async def authenticate(self, request) -> bool:
            from lab_manager.config import get_settings

            settings = get_settings()
            if not settings.auth_enabled:
                return True
            return request.session.get("authenticated", False)

    from lab_manager.config import get_settings

    settings = get_settings()
    secret = settings.admin_secret_key or settings.api_key
    if not secret:
        import secrets

        secret = secrets.token_hex(32)
    return AdminAuthBackend(secret_key=secret)


def setup_admin(app, engine):
    auth_backend = _make_auth_backend()
    admin = Admin(
        app, engine, title="LabClaw Manager", authentication_backend=auth_backend
    )
    admin.add_view(VendorAdmin)
    admin.add_view(ProductAdmin)
    admin.add_view(StaffAdmin)
    admin.add_view(LocationAdmin)
    admin.add_view(OrderAdmin)
    admin.add_view(OrderItemAdmin)
    admin.add_view(InventoryAdmin)
    admin.add_view(DocumentAdmin)
    admin.add_view(AuditLogAdmin)
    admin.add_view(AlertAdmin)
