from datetime import date, datetime, timedelta
from decimal import Decimal

import plotly.express as px
import streamlit as st
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError

from config import get_settings, validate_runtime
from ai.analyst import run_analyst_query
from ai.gemini_provider import GeminiProvider
from ai.openrouter_provider import OpenRouterProvider
from database.connection import SessionLocal, engine
from database.migrations import apply_sqlite_dev_migrations
from database.models import AuditLog, Base, Business, BusinessMembership, Customer, Document, Payment, Product, Purchase, Return, Sale, SaleItem, Supplier, User
from security.authentication import clear_login_failures, hash_password, login_allowed, record_login_failure, verify_password
from security.authorization import require_role
from services.inventory_service import adjust_stock, create_product
from services.sales_service import SaleLine, record_payment, record_sale
from services.purchase_service import PurchaseLine, record_purchase, record_supplier_payment
from services.reporting_service import business_report
from services.document_service import extract_document, safe_document_context, save_document, search_chunks
from services.return_service import record_sale_return
from services.user_service import create_employee
from services.invoice_service import extract_invoice_draft
from services.cancellation_service import cancel_sale


settings = get_settings()
validate_runtime(settings)
st.set_page_config(page_title="LedgerLens", page_icon="LL", layout="wide")
if settings.auto_create_schema:
    Base.metadata.create_all(engine)
    apply_sqlite_dev_migrations()


def format_inr(amount: Decimal | int | float | None) -> str:
    value = Decimal(str(amount or 0))
    return f"Rs {value:,.2f}"


def load_summary(business_id: int) -> tuple[int, int, Decimal]:
    with SessionLocal() as session:
        business_count = session.scalar(select(func.count(Business.id)).where(Business.id == business_id)) or 0
        product_count = session.scalar(
            select(func.count(Product.id)).where(Product.business_id == business_id)
        ) or 0
        inventory_value = session.scalar(
            select(func.coalesce(func.sum(Product.stock_quantity * Product.cost_price), 0)).where(
                Product.business_id == business_id
            )
        ) or Decimal("0")
        return business_count, product_count, Decimal(str(inventory_value))


def setup_business() -> None:
    st.title("Set up LedgerLens")
    st.caption("Create the first business owner account. Passwords are stored as bcrypt hashes.")
    with st.form("business_setup"):
        business_name = st.text_input("Business name", placeholder="Mehta Electronics")
        address = st.text_area("Address", placeholder="Jaipur, Rajasthan")
        contact = st.text_input("Contact number or email")
        owner_name = st.text_input("Owner full name")
        email = st.text_input("Owner email")
        password = st.text_input("Password", type="password", help="Use at least 8 characters.")
        confirm_password = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create business", type="primary")

    if not submitted:
        return
    if not all(value.strip() for value in (business_name, owner_name, email, password)):
        st.error("Business name, owner name, email, and password are required.")
        return
    if len(password) < 8:
        st.error("Password must contain at least 8 characters.")
        return
    if password != confirm_password:
        st.error("Passwords do not match.")
        return

    try:
        with SessionLocal.begin() as session:
            user = User(email=email.strip().lower(), password_hash=hash_password(password), full_name=owner_name.strip())
            business = Business(name=business_name.strip(), address=address.strip() or None, contact=contact.strip() or None)
            session.add_all([user, business])
            session.flush()
            session.add(BusinessMembership(business_id=business.id, user_id=user.id, role="owner"))
        st.success("Business created. Please sign in.")
        st.rerun()
    except IntegrityError:
        st.error("That email is already registered. Use another email address.")


def login() -> None:
    st.title("LedgerLens")
    st.caption("Sign in to your business workspace.")
    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")
    if not submitted:
        return
    normalized_email = email.strip().lower()
    if not login_allowed(normalized_email):
        st.error("Too many failed attempts. Try again in 15 minutes.")
        return
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == normalized_email, User.is_active.is_(True)))
        if user is None or not verify_password(password, user.password_hash):
            record_login_failure(normalized_email)
            st.error("Invalid email or password.")
            return
        membership = session.scalar(select(BusinessMembership).where(BusinessMembership.user_id == user.id))
        if membership is None:
            st.error("Your account is not linked to an active business.")
            return
        clear_login_failures(normalized_email)
        st.session_state.user_id = user.id
        st.session_state.business_id = membership.business_id
        st.session_state.role = membership.role
        st.session_state.last_activity = datetime.now().timestamp()
        st.rerun()


def inventory_page() -> None:
    business_id = st.session_state.business_id
    st.title("Products & Inventory")
    st.caption("Track products, opening stock, prices, and authorized stock adjustments.")
    add_tab, adjust_tab, list_tab = st.tabs(["Add product", "Adjust stock", "Product list"])

    with add_tab:
        with st.form("add_product"):
            name = st.text_input("Product name")
            sku = st.text_input("SKU", help="SKU is unique within this business.")
            price_col, selling_col = st.columns(2)
            cost_price = price_col.number_input("Cost price (INR)", min_value=0.0, step=100.0)
            selling_price = selling_col.number_input("Selling price (INR)", min_value=0.0, step=100.0)
            stock_quantity = st.number_input("Opening stock", min_value=0, step=1)
            low_stock_threshold = st.number_input("Low-stock threshold", min_value=0, value=5, step=1)
            submitted = st.form_submit_button("Add product", type="primary")
        if submitted:
            try:
                with SessionLocal() as session:
                    require_role(
                        session, user_id=st.session_state.user_id,
                        business_id=business_id, allowed_roles={"owner"},
                    )
            except PermissionError as error:
                st.error(str(error))
                return
            try:
                with SessionLocal.begin() as session:
                    create_product(
                        session, business_id=business_id, name=name, sku=sku,
                        cost_price=Decimal(str(cost_price)), selling_price=Decimal(str(selling_price)),
                        stock_quantity=stock_quantity, low_stock_threshold=low_stock_threshold,
                        user_id=st.session_state.user_id,
                    )
                st.success("Product added successfully.")
            except ValueError as error:
                st.error(str(error))

    with adjust_tab:
        with SessionLocal() as session:
            products = session.scalars(
                select(Product).where(Product.business_id == business_id).order_by(Product.name)
            ).all()
        if not products:
            st.info("Add a product before making a stock adjustment.")
        else:
            product_options = {f"{product.name} ({product.sku})": product.id for product in products}
            with st.form("adjust_stock"):
                selected_product = st.selectbox("Product", list(product_options))
                quantity_delta = st.number_input("Quantity change", value=0, step=1)
                reason = st.text_input("Reason", placeholder="Damaged item, stock count, or correction")
                submitted = st.form_submit_button("Save adjustment", type="primary")
            if submitted:
                try:
                    with SessionLocal() as session:
                        require_role(
                            session, user_id=st.session_state.user_id,
                            business_id=business_id, allowed_roles={"owner"},
                        )
                    with SessionLocal.begin() as session:
                        adjust_stock(
                            session, business_id=business_id,
                            product_id=product_options[selected_product],
                            quantity_delta=quantity_delta, reason=reason, user_id=st.session_state.user_id,
                        )
                    st.success("Stock adjustment saved.")
                except ValueError as error:
                    st.error(str(error))

    with list_tab:
        with SessionLocal() as session:
            products = session.scalars(
                select(Product).where(Product.business_id == business_id).order_by(Product.name)
            ).all()
        if products:
            st.dataframe(
                [
                    {
                        "Name": product.name,
                        "SKU": product.sku,
                        "Stock": product.stock_quantity,
                        "Cost": format_inr(product.cost_price),
                        "Selling price": format_inr(product.selling_price),
                        "Status": "Low stock" if product.stock_quantity <= product.low_stock_threshold else "In stock",
                    }
                    for product in products
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No products yet. Add your first product to begin tracking inventory.")


def sales_page() -> None:
    business_id = st.session_state.business_id
    st.title("Sales & Payments")
    st.caption("Record sales, partial payments, and later collections. Revenue and cash collected are separate.")
    sale_tab, customer_tab, receivable_tab, return_tab, cancel_tab = st.tabs(
        ["New sale", "Customers", "Receivables", "Returns", "Cancellations"]
    )

    with customer_tab:
        with st.form("add_customer"):
            customer_name = st.text_input("Customer name")
            customer_contact = st.text_input("Contact")
            submitted = st.form_submit_button("Add customer")
        if submitted:
            if not customer_name.strip():
                st.error("Customer name is required.")
            else:
                with SessionLocal.begin() as session:
                    session.add(Customer(
                        business_id=business_id,
                        name=customer_name.strip(),
                        contact=customer_contact.strip() or None,
                    ))
                st.success("Customer added.")
        with SessionLocal() as session:
            customers = session.scalars(
                select(Customer).where(Customer.business_id == business_id).order_by(Customer.name)
            ).all()
        if customers:
            st.dataframe(
                [{"Name": customer.name, "Contact": customer.contact or ""} for customer in customers],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No customers yet. Walk-in sales can be recorded without a customer.")

    with sale_tab:
        with SessionLocal() as session:
            products = session.scalars(
                select(Product).where(Product.business_id == business_id, Product.stock_quantity > 0)
                .order_by(Product.name)
            ).all()
            customers = session.scalars(
                select(Customer).where(Customer.business_id == business_id).order_by(Customer.name)
            ).all()
        if not products:
            st.info("Add products with available stock before recording a sale.")
        else:
            product_options = {f"{product.name} ({product.sku})": product for product in products}
            customer_options = {"Walk-in customer": None}
            customer_options.update({f"{customer.name} ({customer.contact or 'no contact'})": customer.id for customer in customers})
            with st.form("new_sale"):
                selected_product = st.selectbox("Product", list(product_options))
                quantity = st.number_input("Quantity", min_value=1, value=1, step=1)
                selected_customer = st.selectbox("Customer", list(customer_options))
                discount = st.number_input("Discount (INR)", min_value=0.0, value=0.0, step=100.0)
                amount_paid = st.number_input("Amount paid now (INR)", min_value=0.0, value=0.0, step=100.0)
                payment_method = st.selectbox("Payment method", ["cash", "upi", "card", "bank transfer", "other"])
                reference = st.text_input("Sale reference", help="Use a receipt or invoice reference to prevent duplicate submissions.")
                submitted = st.form_submit_button("Confirm sale", type="primary")
            if submitted:
                try:
                    with SessionLocal.begin() as session:
                        sale = record_sale(
                            session,
                            business_id=business_id,
                            lines=[SaleLine(product_id=product_options[selected_product].id, quantity=quantity)],
                            amount_paid=Decimal(str(amount_paid)),
                            payment_method=payment_method,
                            customer_id=customer_options[selected_customer],
                            discount=Decimal(str(discount)),
                            reference=reference.strip() or None,
                            user_id=st.session_state.user_id,
                        )
                    outstanding = sale.total_amount - Decimal(str(amount_paid))
                    st.success(f"Sale #{sale.id} recorded. Outstanding: {format_inr(outstanding)}")
                except ValueError as error:
                    st.error(str(error))

    with receivable_tab:
        with SessionLocal() as session:
            sales = session.scalars(
                select(Sale).where(Sale.business_id == business_id, Sale.status == "confirmed")
                .order_by(Sale.created_at.desc())
            ).all()
            customers_by_id = {
                customer.id: customer.name
                for customer in session.scalars(select(Customer).where(Customer.business_id == business_id)).all()
            }
            payments = session.scalars(
                select(Payment).where(Payment.business_id == business_id)
            ).all()
        payments_by_sale: dict[int, Decimal] = {}
        for payment in payments:
            if payment.sale_id is not None:
                payments_by_sale[payment.sale_id] = payments_by_sale.get(payment.sale_id, Decimal("0.00")) + payment.amount
        outstanding_sales = [sale for sale in sales if payments_by_sale.get(sale.id, Decimal("0.00")) < sale.total_amount]
        if outstanding_sales:
            st.dataframe(
                [
                    {
                        "Sale": sale.reference or f"#{sale.id}",
                        "Customer": customers_by_id.get(sale.customer_id, "Walk-in"),
                        "Total": format_inr(sale.total_amount),
                        "Collected": format_inr(payments_by_sale.get(sale.id, Decimal("0.00"))),
                        "Outstanding": format_inr(sale.total_amount - payments_by_sale.get(sale.id, Decimal("0.00"))),
                    }
                    for sale in outstanding_sales
                ],
                use_container_width=True,
                hide_index=True,
            )
            sale_options = {sale.reference or f"Sale #{sale.id}": sale for sale in outstanding_sales}
            with st.form("record_payment"):
                selected_sale = st.selectbox("Sale", list(sale_options))
                payment_amount = st.number_input("Payment amount (INR)", min_value=0.01, step=100.0)
                payment_method = st.selectbox("Method", ["cash", "upi", "card", "bank transfer", "other"], key="receivable_method")
                submitted = st.form_submit_button("Record payment", type="primary")
            if submitted:
                sale = sale_options[selected_sale]
                try:
                    with SessionLocal.begin() as session:
                        record_payment(
                            session, business_id=business_id, sale_id=sale.id,
                            amount=Decimal(str(payment_amount)), method=payment_method,
                            user_id=st.session_state.user_id,
                        )
                    st.success("Payment recorded against the sale.")
                except ValueError as error:
                    st.error(str(error))
        else:
            st.info("No outstanding customer balances.")

    with return_tab:
        with SessionLocal() as session:
            sales = session.scalars(
                select(Sale).where(Sale.business_id == business_id, Sale.status == "confirmed")
                .order_by(Sale.created_at.desc())
            ).all()
        if not sales:
            st.info("No confirmed sales are available for return.")
        else:
            sale_options = {sale.reference or f"Sale #{sale.id}": sale.id for sale in sales}
            selected_sale = st.selectbox("Sale to return", list(sale_options), key="return_sale")
            with SessionLocal() as session:
                sale_items = session.scalars(
                    select(SaleItem).where(SaleItem.sale_id == sale_options[selected_sale])
                ).all()
                products_by_id = {
                    product.id: product.name
                    for product in session.scalars(select(Product).where(Product.business_id == business_id)).all()
                }
            if sale_items:
                item_options = {
                    f"{products_by_id.get(item.product_id, 'Product')} | sold qty {item.quantity} | {format_inr(item.unit_price)}": item
                    for item in sale_items
                }
                with st.form("record_return"):
                    selected_item = st.selectbox("Sale item", list(item_options))
                    return_quantity = st.number_input("Return quantity", min_value=1, value=1, step=1)
                    return_reason = st.text_input("Return reason")
                    refund_method = st.selectbox("Refund method", ["cash", "upi", "card", "bank transfer", "other"])
                    submitted = st.form_submit_button("Confirm return", type="primary")
                if submitted:
                    try:
                        with SessionLocal() as session:
                            require_role(
                                session, user_id=st.session_state.user_id,
                                business_id=business_id, allowed_roles={"owner"},
                            )
                        with SessionLocal.begin() as session:
                            returned = record_sale_return(
                                session, business_id=business_id, sale_id=sale_options[selected_sale],
                                items={item_options[selected_item].id: return_quantity}, reason=return_reason,
                                user_id=st.session_state.user_id, refund_method=refund_method,
                            )
                        st.success(f"Return #{returned.id} recorded. Refund value: {format_inr(returned.total_amount)}")
                    except (PermissionError, ValueError) as error:
                        st.error(str(error))

    with cancel_tab:
        with SessionLocal() as session:
            sales = session.scalars(
                select(Sale).where(Sale.business_id == business_id, Sale.status == "confirmed")
                .order_by(Sale.created_at.desc())
            ).all()
        if sales:
            sale_options = {sale.reference or f"Sale #{sale.id}": sale.id for sale in sales}
            with st.form("cancel_sale"):
                selected_sale = st.selectbox("Sale to cancel", list(sale_options), key="cancel_sale_select")
                cancel_reason = st.text_input("Cancellation reason")
                submitted = st.form_submit_button("Cancel sale", type="primary")
            if submitted:
                try:
                    with SessionLocal() as session:
                        require_role(
                            session, user_id=st.session_state.user_id,
                            business_id=business_id, allowed_roles={"owner"},
                        )
                    with SessionLocal.begin() as session:
                        cancel_sale(
                            session, business_id=business_id, sale_id=sale_options[selected_sale],
                            reason=cancel_reason, user_id=st.session_state.user_id,
                        )
                    st.success("Sale cancelled and stock restored.")
                except (PermissionError, ValueError) as error:
                    st.error(str(error))
        else:
            st.info("No confirmed sales are available for cancellation.")


def purchases_page() -> None:
    business_id = st.session_state.business_id
    try:
        with SessionLocal() as session:
            require_role(
                session, user_id=st.session_state.user_id,
                business_id=business_id, allowed_roles={"owner"},
            )
    except PermissionError as error:
        st.error(str(error))
        return
    st.title("Suppliers & Purchases")
    st.caption("Record supplier purchases separately from sales. Confirmed purchases increase stock and create payables.")
    purchase_tab, supplier_tab, payable_tab = st.tabs(["New purchase", "Suppliers", "Payables"])

    with supplier_tab:
        with st.form("add_supplier"):
            supplier_name = st.text_input("Supplier name")
            supplier_contact = st.text_input("Contact", key="supplier_contact")
            submitted = st.form_submit_button("Add supplier")
        if submitted:
            if not supplier_name.strip():
                st.error("Supplier name is required.")
            else:
                with SessionLocal.begin() as session:
                    session.add(Supplier(
                        business_id=business_id,
                        name=supplier_name.strip(),
                        contact=supplier_contact.strip() or None,
                    ))
                st.success("Supplier added.")
        with SessionLocal() as session:
            suppliers = session.scalars(
                select(Supplier).where(Supplier.business_id == business_id).order_by(Supplier.name)
            ).all()
        if suppliers:
            st.dataframe(
                [{"Name": supplier.name, "Contact": supplier.contact or ""} for supplier in suppliers],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No suppliers yet. Add a supplier before recording purchases.")

    with purchase_tab:
        with SessionLocal() as session:
            products = session.scalars(
                select(Product).where(Product.business_id == business_id).order_by(Product.name)
            ).all()
            suppliers = session.scalars(
                select(Supplier).where(Supplier.business_id == business_id).order_by(Supplier.name)
            ).all()
        if not products or not suppliers:
            st.info("Add at least one product and supplier before recording a purchase.")
        else:
            product_options = {f"{product.name} ({product.sku})": product for product in products}
            supplier_options = {f"{supplier.name} ({supplier.contact or 'no contact'})": supplier.id for supplier in suppliers}
            with st.form("new_purchase"):
                selected_supplier = st.selectbox("Supplier", list(supplier_options))
                selected_product = st.selectbox("Product", list(product_options))
                quantity = st.number_input("Quantity", min_value=1, value=1, step=1, key="purchase_quantity")
                unit_cost = st.number_input("Unit cost (INR)", min_value=0.0, step=100.0)
                amount_paid = st.number_input("Amount paid now (INR)", min_value=0.0, step=100.0, key="purchase_paid")
                payment_method = st.selectbox("Payment method", ["cash", "upi", "card", "bank transfer", "other"], key="purchase_method")
                reference = st.text_input("Purchase reference", help="Supplier invoice or purchase-order reference.")
                submitted = st.form_submit_button("Confirm purchase", type="primary")
            if submitted:
                try:
                    with SessionLocal.begin() as session:
                        purchase = record_purchase(
                            session,
                            business_id=business_id,
                            supplier_id=supplier_options[selected_supplier],
                            lines=[PurchaseLine(
                                product_id=product_options[selected_product].id,
                                quantity=quantity,
                                unit_cost=Decimal(str(unit_cost)),
                            )],
                            amount_paid=Decimal(str(amount_paid)),
                            payment_method=payment_method,
                            reference=reference.strip() or None,
                            user_id=st.session_state.user_id,
                        )
                    outstanding = purchase.total_amount - Decimal(str(amount_paid))
                    st.success(f"Purchase #{purchase.id} recorded. Payable: {format_inr(outstanding)}")
                except ValueError as error:
                    st.error(str(error))

    with payable_tab:
        with SessionLocal() as session:
            purchases = session.scalars(
                select(Purchase).where(Purchase.business_id == business_id, Purchase.status == "confirmed")
                .order_by(Purchase.created_at.desc())
            ).all()
            suppliers_by_id = {
                supplier.id: supplier.name
                for supplier in session.scalars(select(Supplier).where(Supplier.business_id == business_id)).all()
            }
            payments = session.scalars(select(Payment).where(Payment.business_id == business_id)).all()
        payments_by_purchase: dict[int, Decimal] = {}
        for payment in payments:
            if payment.purchase_id is not None:
                payments_by_purchase[payment.purchase_id] = payments_by_purchase.get(payment.purchase_id, Decimal("0.00")) + payment.amount
        outstanding_purchases = [
            purchase for purchase in purchases
            if payments_by_purchase.get(purchase.id, Decimal("0.00")) < purchase.total_amount
        ]
        if outstanding_purchases:
            st.dataframe(
                [
                    {
                        "Purchase": purchase.reference or f"#{purchase.id}",
                        "Supplier": suppliers_by_id.get(purchase.supplier_id, "Unknown"),
                        "Total": format_inr(purchase.total_amount),
                        "Paid": format_inr(payments_by_purchase.get(purchase.id, Decimal("0.00"))),
                        "Outstanding": format_inr(purchase.total_amount - payments_by_purchase.get(purchase.id, Decimal("0.00"))),
                    }
                    for purchase in outstanding_purchases
                ],
                use_container_width=True,
                hide_index=True,
            )
            purchase_options = {purchase.reference or f"Purchase #{purchase.id}": purchase for purchase in outstanding_purchases}
            with st.form("record_supplier_payment"):
                selected_purchase = st.selectbox("Purchase", list(purchase_options))
                payment_amount = st.number_input("Payment amount (INR)", min_value=0.01, step=100.0, key="supplier_payment_amount")
                payment_method = st.selectbox("Method", ["cash", "upi", "card", "bank transfer", "other"], key="supplier_payment_method")
                submitted = st.form_submit_button("Record supplier payment", type="primary")
            if submitted:
                purchase = purchase_options[selected_purchase]
                try:
                    with SessionLocal.begin() as session:
                        record_supplier_payment(
                            session, business_id=business_id, purchase_id=purchase.id,
                            amount=Decimal(str(payment_amount)), method=payment_method,
                            user_id=st.session_state.user_id,
                        )
                    st.success("Supplier payment recorded.")
                except ValueError as error:
                    st.error(str(error))
        else:
            st.info("No outstanding supplier payables.")


def reports_page() -> None:
    business_id = st.session_state.business_id
    st.title("Reports & Analytics")
    st.caption("Calculated from confirmed sales, payments, purchases, and current inventory records.")
    today = date.today()
    filter_col, end_col = st.columns(2)
    start_date = filter_col.date_input("Start date", value=today - timedelta(days=30))
    end_date = end_col.date_input("End date", value=today)
    try:
        with SessionLocal() as session:
            report = business_report(
                session, business_id=business_id, start_date=start_date, end_date=end_date
            )
    except ValueError as error:
        st.error(str(error))
        return

    metric_one, metric_two, metric_three, metric_four = st.columns(4)
    metric_one.metric("Revenue", format_inr(report["revenue"]))
    metric_two.metric("Cash collected", format_inr(report["cash_collected"]))
    metric_three.metric("Customer receivables", format_inr(report["customer_receivables"]))
    metric_four.metric("Inventory value", format_inr(report["inventory_value"]))
    st.divider()
    purchase_col, payable_col, profit_col = st.columns(3)
    purchase_col.metric("Purchases", format_inr(report["purchases"]))
    payable_col.metric("Supplier payables", format_inr(report["supplier_payables"]))
    if report["gross_profit_available"]:
        profit_col.metric("Gross profit", format_inr(report["gross_profit"]))
    else:
        profit_col.metric("Gross profit", "Unavailable")
    st.caption(f"Confirmed sales: {report['sales_count']} | Confirmed purchases: {report['purchase_count']}")

    if report["gross_profit_available"]:
        st.success("Gross profit uses the cost captured on each sale line.")
    else:
        st.warning("Gross profit is unavailable because one or more historical sale lines have no captured cost.")

    breakdown = report["payment_breakdown"]
    if breakdown:
        st.subheader("Sales collections by payment method")
        chart_data = [{"Method": method, "Amount": float(amount)} for method, amount in breakdown.items()]
        st.plotly_chart(
            px.bar(chart_data, x="Method", y="Amount", labels={"Amount": "INR collected"}),
            use_container_width=True,
        )
    else:
        st.info("No customer payments were recorded in this date range.")

    export_rows = [
        ("Revenue", report["revenue"]),
        ("Cash collected", report["cash_collected"]),
        ("Customer receivables", report["customer_receivables"]),
        ("Purchases", report["purchases"]),
        ("Supplier payables", report["supplier_payables"]),
        ("Gross profit", report["gross_profit"] if report["gross_profit_available"] else "Unavailable"),
        ("Inventory value", report["inventory_value"]),
    ]
    csv = "Metric,Value\n" + "\n".join(f"{name},{value}" for name, value in export_rows)
    st.download_button(
        "Download report CSV", csv,
        file_name=f"ledgerlens-report-{start_date}-{end_date}.csv", mime="text/csv",
    )


def analyst_page() -> None:
    st.title("AI Data Analyst")
    st.caption("Ask questions about this business. The selected AI provider can read data only; it cannot modify records.")
    provider = OpenRouterProvider(settings) if settings.ai_provider.lower() == "openrouter" else GeminiProvider(settings)
    if not provider.configured:
        required_key = "OPENROUTER_API_KEY" if settings.ai_provider.lower() == "openrouter" else "GEMINI_API_KEY"
        st.warning(f"{settings.ai_provider.title()} is not configured. Add {required_key} to .env, then restart Streamlit.")
        st.info("The analyst will reject writes, unknown tables, missing business scope, and oversized queries.")
        return

    question = st.text_area(
        "Business question",
        placeholder="How much did I collect this month, and which payment method was used most?",
    )
    if st.button("Ask Gemini", type="primary"):
        try:
            with SessionLocal() as session:
                result = run_analyst_query(
                    session,
                    provider=provider,
                    question=question,
                    business_id=st.session_state.business_id,
                )
            st.markdown("**Provenance**: `Fact` database rows | `Calculated` SQL result | `AI Interpretation` explanation")
            st.subheader("Answer")
            st.write(result["explanation"])
            if result["rows"]:
                st.dataframe(result["rows"], use_container_width=True, hide_index=True)
            else:
                st.info("The query returned no matching records.")
            with st.expander("Validated query details"):
                st.caption(result["rationale"] or "No rationale supplied.")
                st.code(result["sql"], language="sql")
        except (RuntimeError, ValueError) as error:
            st.error(str(error))


def documents_page() -> None:
    business_id = st.session_state.business_id
    st.title("Business Documents")
    st.caption("Upload supplier policies, manuals, and price lists. Files stay associated with this business.")
    uploaded = st.file_uploader("Upload PDF or CSV", type=["pdf", "csv"])
    if uploaded is not None and st.button("Save document", type="primary"):
        try:
            extracted = extract_document(uploaded.name, uploaded.getvalue())
            with SessionLocal.begin() as session:
                save_document(session, business_id=business_id, extracted=extracted)
            st.success(f"Saved {uploaded.name}. Text was extracted and chunked for search.")
        except ValueError as error:
            st.error(str(error))

    st.subheader("Invoice extraction preview")
    st.caption("Extraction is untrusted and never creates a purchase automatically. Review before saving anything.")
    invoice_file = st.file_uploader("Upload supplier invoice for review", type=["pdf", "csv"], key="invoice_file")
    if invoice_file is not None and st.button("Extract invoice draft"):
        try:
            draft = extract_invoice_draft(invoice_file.name, invoice_file.getvalue())
            st.session_state.invoice_draft = draft
        except ValueError as error:
            st.error(str(error))
    draft = st.session_state.get("invoice_draft")
    if draft:
        st.warning("Review required: this preview has not created a purchase or changed inventory.")
        st.write({
            "Supplier": draft.supplier_name or "Not detected",
            "Invoice number": draft.invoice_number or "Not detected",
            "Total": str(draft.total) if draft.total is not None else "Not detected",
        })
        if draft.lines:
            st.dataframe([
                {"Product": line.product_name, "Quantity": line.quantity, "Unit cost": str(line.unit_cost)}
                for line in draft.lines
            ], use_container_width=True, hide_index=True)
        for warning in draft.warnings:
            st.warning(warning)

    with SessionLocal() as session:
        documents = session.scalars(
            select(Document).where(Document.business_id == business_id).order_by(Document.created_at.desc())
        ).all()
    if documents:
        st.subheader("Uploaded documents")
        st.dataframe(
            [{"Filename": document.filename, "Type": document.file_type.upper(), "Added": document.created_at} for document in documents],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No documents uploaded yet.")

    st.subheader("Search extracted text")
    query = st.text_input("Search terms", placeholder="return policy warranty")
    if query.strip():
        with SessionLocal() as session:
            chunks = search_chunks(session, business_id=business_id, query=query)
        if chunks:
            st.markdown("**Provenance**: `Fact` extracted document text | `Insufficient Data` when no matches exist")
            st.info(safe_document_context(chunks))
        else:
            st.warning("Insufficient Data: no uploaded document contains those search terms.")


def settings_page() -> None:
    business_id = st.session_state.business_id
    if st.session_state.get("role") != "owner":
        st.error("Only the business owner can manage settings and employees.")
        return
    st.title("Settings")
    st.caption("Manage employee access. Employees cannot change stock or confirm purchases.")
    with st.form("create_employee"):
        full_name = st.text_input("Employee full name")
        email = st.text_input("Employee email")
        password = st.text_input("Temporary password", type="password")
        submitted = st.form_submit_button("Create employee", type="primary")
    if submitted:
        try:
            with SessionLocal.begin() as session:
                employee = create_employee(
                    session, business_id=business_id, full_name=full_name,
                    email=email, password=password,
                )
            st.success(f"Employee {employee.full_name} created.")
        except ValueError as error:
            st.error(str(error))

    with SessionLocal() as session:
        memberships = session.scalars(
            select(BusinessMembership).where(BusinessMembership.business_id == business_id)
        ).all()
        users = {user.id: user for user in session.scalars(select(User)).all()}
    st.subheader("Business members")
    st.dataframe(
        [
            {"Name": users[membership.user_id].full_name, "Email": users[membership.user_id].email, "Role": membership.role}
            for membership in memberships if membership.user_id in users
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Change your password")
    with st.form("change_password"):
        current_password = st.text_input("Current password", type="password")
        new_password = st.text_input("New password", type="password")
        confirm_password = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button("Change password")
    if submitted:
        if new_password != confirm_password:
            st.error("New passwords do not match.")
        elif len(new_password) < 8:
            st.error("New password must contain at least 8 characters.")
        else:
            with SessionLocal.begin() as session:
                user = session.get(User, st.session_state.user_id)
                if user is None or not verify_password(current_password, user.password_hash):
                    st.error("Current password is incorrect.")
                else:
                    user.password_hash = hash_password(new_password)
                    st.success("Password changed successfully.")


def audit_page() -> None:
    if st.session_state.get("role") != "owner":
        st.error("Only the business owner can view the audit history.")
        return
    business_id = st.session_state.business_id
    st.title("Audit History")
    st.caption("Immutable operational history for financial and inventory actions.")
    with SessionLocal() as session:
        entries = session.scalars(
            select(AuditLog).where(AuditLog.business_id == business_id)
            .order_by(AuditLog.created_at.desc()).limit(500)
        ).all()
        users = {user.id: user.full_name for user in session.scalars(select(User)).all()}
    if not entries:
        st.info("No audit events recorded yet.")
        return
    st.dataframe(
        [
            {
                "Time": entry.created_at,
                "Actor": users.get(entry.user_id, "System/unknown"),
                "Action": entry.action,
                "Entity": f"{entry.entity_type} #{entry.entity_id or '-'}",
                "Details": entry.details or "",
            }
            for entry in entries
        ],
        use_container_width=True,
        hide_index=True,
    )


def dashboard() -> None:
    last_activity = st.session_state.get("last_activity", datetime.now().timestamp())
    if datetime.now().timestamp() - last_activity > settings.session_timeout_minutes * 60:
        st.session_state.clear()
        st.warning("Your session expired. Please sign in again.")
        st.rerun()
    st.session_state.last_activity = datetime.now().timestamp()
    business_count, product_count, inventory_value = load_summary(st.session_state.business_id)
    with st.sidebar:
        st.header("LedgerLens")
        st.caption(f"Environment: {settings.app_env}")
        page = st.radio(
            "Workspace",
            [
                "Dashboard",
                "Products & Inventory",
                "Sales & Payments",
                "Suppliers & Purchases",
                "Reports & Analytics",
                "AI Data Analyst",
                "Documents",
                "Settings",
                "Audit History",
            ],
            label_visibility="collapsed",
        )
        if settings.gemini_api_key:
            st.caption(f"Gemini configured: {settings.gemini_model}")
        else:
            st.caption("Gemini API key not configured yet")
        if st.button("Sign out"):
            st.session_state.clear()
            st.rerun()

    if page == "Products & Inventory":
        inventory_page()
        return
    if page == "Sales & Payments":
        sales_page()
        return
    if page == "Suppliers & Purchases":
        purchases_page()
        return
    if page == "Reports & Analytics":
        reports_page()
        return
    if page == "AI Data Analyst":
        analyst_page()
        return
    if page == "Documents":
        documents_page()
        return
    if page == "Settings":
        settings_page()
        return
    if page == "Audit History":
        audit_page()
        return

    st.title("LedgerLens")
    st.caption("AI finance and operations copilot | Phase 1 foundation")
    metric_one, metric_two, metric_three = st.columns(3)
    metric_one.metric("Businesses", business_count)
    metric_two.metric("Products", product_count)
    metric_three.metric("Inventory value", format_inr(inventory_value))
    st.divider()
    st.subheader("Dashboard")
    st.success("Database connection is active.")
    st.info("Sales, customers, suppliers, reports, and AI analysis will be added phase by phase.")


try:
    with SessionLocal() as session:
        has_users = session.scalar(select(func.count(User.id))) or 0
except OperationalError:
    st.error("LedgerLens could not connect to the configured database.")
    st.info(
        "Check Streamlit Cloud Secrets: DATABASE_URL must use the Supabase "
        "Session Pooler host, the correct password, and a URL-encoded password "
        "if it contains characters such as @, #, :, /, %, ?, or &. "
        "After saving Secrets, reboot the app."
    )
    st.stop()

if has_users == 0:
    setup_business()
elif "user_id" not in st.session_state:
    login()
else:
    dashboard()
