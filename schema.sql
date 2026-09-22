
CREATE TABLE businesses (
	id SERIAL NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	address TEXT, 
	contact VARCHAR(100), 
	currency VARCHAR(3) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);


CREATE TABLE users (
	id SERIAL NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	full_name VARCHAR(200) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email)
);


CREATE TABLE business_memberships (
	id SERIAL NOT NULL, 
	business_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	role VARCHAR(30) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_business_user UNIQUE (business_id, user_id), 
	FOREIGN KEY(business_id) REFERENCES businesses (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_business_memberships_user_id ON business_memberships (user_id);

CREATE INDEX ix_business_memberships_business_id ON business_memberships (business_id);


CREATE TABLE product_categories (
	id SERIAL NOT NULL, 
	business_id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(business_id) REFERENCES businesses (id)
);

CREATE INDEX ix_product_categories_business_id ON product_categories (business_id);


CREATE TABLE suppliers (
	id SERIAL NOT NULL, 
	business_id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	contact VARCHAR(100), 
	PRIMARY KEY (id), 
	FOREIGN KEY(business_id) REFERENCES businesses (id)
);

CREATE INDEX ix_suppliers_business_id ON suppliers (business_id);


CREATE TABLE customers (
	id SERIAL NOT NULL, 
	business_id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	contact VARCHAR(100), 
	PRIMARY KEY (id), 
	FOREIGN KEY(business_id) REFERENCES businesses (id)
);

CREATE INDEX ix_customers_business_id ON customers (business_id);


CREATE TABLE documents (
	id SERIAL NOT NULL, 
	business_id INTEGER NOT NULL, 
	filename VARCHAR(255) NOT NULL, 
	file_type VARCHAR(20) NOT NULL, 
	content_text TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(business_id) REFERENCES businesses (id)
);

CREATE INDEX ix_documents_business_id ON documents (business_id);


CREATE TABLE audit_logs (
	id SERIAL NOT NULL, 
	business_id INTEGER NOT NULL, 
	user_id INTEGER, 
	action VARCHAR(80) NOT NULL, 
	entity_type VARCHAR(80) NOT NULL, 
	entity_id INTEGER, 
	details TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(business_id) REFERENCES businesses (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_audit_logs_business_id ON audit_logs (business_id);

CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id);


CREATE TABLE products (
	id SERIAL NOT NULL, 
	business_id INTEGER NOT NULL, 
	category_id INTEGER, 
	supplier_id INTEGER, 
	name VARCHAR(200) NOT NULL, 
	sku VARCHAR(80) NOT NULL, 
	cost_price NUMERIC(12, 2) NOT NULL, 
	selling_price NUMERIC(12, 2) NOT NULL, 
	stock_quantity INTEGER NOT NULL, 
	low_stock_threshold INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_product_business_sku UNIQUE (business_id, sku), 
	FOREIGN KEY(business_id) REFERENCES businesses (id), 
	FOREIGN KEY(category_id) REFERENCES product_categories (id), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id)
);

CREATE INDEX ix_products_business_id ON products (business_id);


CREATE TABLE sales (
	id SERIAL NOT NULL, 
	business_id INTEGER NOT NULL, 
	customer_id INTEGER, 
	reference VARCHAR(80), 
	total_amount NUMERIC(12, 2) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_sale_business_reference UNIQUE (business_id, reference), 
	FOREIGN KEY(business_id) REFERENCES businesses (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id)
);

CREATE INDEX ix_sales_business_id ON sales (business_id);


CREATE TABLE purchases (
	id SERIAL NOT NULL, 
	business_id INTEGER NOT NULL, 
	supplier_id INTEGER, 
	reference VARCHAR(80), 
	total_amount NUMERIC(12, 2) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_purchase_business_reference UNIQUE (business_id, reference), 
	FOREIGN KEY(business_id) REFERENCES businesses (id), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id)
);

CREATE INDEX ix_purchases_business_id ON purchases (business_id);


CREATE TABLE document_chunks (
	id SERIAL NOT NULL, 
	business_id INTEGER NOT NULL, 
	document_id INTEGER NOT NULL, 
	chunk_index INTEGER NOT NULL, 
	page_number INTEGER, 
	content TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(business_id) REFERENCES businesses (id), 
	FOREIGN KEY(document_id) REFERENCES documents (id)
);

CREATE INDEX ix_document_chunks_business_id ON document_chunks (business_id);

CREATE INDEX ix_document_chunks_document_id ON document_chunks (document_id);


CREATE TABLE sale_items (
	id SERIAL NOT NULL, 
	sale_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity INTEGER NOT NULL, 
	unit_price NUMERIC(12, 2) NOT NULL, 
	unit_cost NUMERIC(12, 2), 
	PRIMARY KEY (id), 
	FOREIGN KEY(sale_id) REFERENCES sales (id), 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE INDEX ix_sale_items_sale_id ON sale_items (sale_id);


CREATE TABLE payments (
	id SERIAL NOT NULL, 
	business_id INTEGER NOT NULL, 
	sale_id INTEGER, 
	purchase_id INTEGER, 
	amount NUMERIC(12, 2) NOT NULL, 
	method VARCHAR(30) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(business_id) REFERENCES businesses (id), 
	FOREIGN KEY(sale_id) REFERENCES sales (id), 
	FOREIGN KEY(purchase_id) REFERENCES purchases (id)
);

CREATE INDEX ix_payments_business_id ON payments (business_id);


CREATE TABLE purchase_items (
	id SERIAL NOT NULL, 
	purchase_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity INTEGER NOT NULL, 
	unit_cost NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(purchase_id) REFERENCES purchases (id), 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE INDEX ix_purchase_items_purchase_id ON purchase_items (purchase_id);


CREATE TABLE inventory_movements (
	id SERIAL NOT NULL, 
	business_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity_delta INTEGER NOT NULL, 
	reason VARCHAR(100) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(business_id) REFERENCES businesses (id), 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE INDEX ix_inventory_movements_business_id ON inventory_movements (business_id);


CREATE TABLE returns (
	id SERIAL NOT NULL, 
	business_id INTEGER NOT NULL, 
	sale_id INTEGER NOT NULL, 
	total_amount NUMERIC(12, 2) NOT NULL, 
	reason VARCHAR(255) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(business_id) REFERENCES businesses (id), 
	FOREIGN KEY(sale_id) REFERENCES sales (id)
);

CREATE INDEX ix_returns_business_id ON returns (business_id);

CREATE INDEX ix_returns_sale_id ON returns (sale_id);


CREATE TABLE return_items (
	id SERIAL NOT NULL, 
	return_id INTEGER NOT NULL, 
	sale_item_id INTEGER NOT NULL, 
	quantity INTEGER NOT NULL, 
	unit_price NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(return_id) REFERENCES returns (id), 
	FOREIGN KEY(sale_item_id) REFERENCES sale_items (id)
);

CREATE INDEX ix_return_items_return_id ON return_items (return_id);


CREATE TABLE refunds (
	id SERIAL NOT NULL, 
	business_id INTEGER NOT NULL, 
	return_id INTEGER NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	method VARCHAR(30) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(business_id) REFERENCES businesses (id), 
	UNIQUE (return_id), 
	FOREIGN KEY(return_id) REFERENCES returns (id)
);

CREATE INDEX ix_refunds_business_id ON refunds (business_id);
