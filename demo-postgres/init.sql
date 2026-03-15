-- ============================================================
--  Demo retail database  —  init.sql
--  Auto-loaded by Postgres on first container start
-- ============================================================

CREATE TABLE customers (
    customer_id  SERIAL PRIMARY KEY,
    first_name   VARCHAR(50),
    last_name    VARCHAR(50),
    email        VARCHAR(120) UNIQUE,
    country      VARCHAR(50),
    age          INT,
    signup_date  DATE,
    is_premium   BOOLEAN DEFAULT FALSE
);

CREATE TABLE products (
    product_id   SERIAL PRIMARY KEY,
    name         VARCHAR(120),
    category     VARCHAR(60),
    unit_price   NUMERIC(10,2),
    stock_qty    INT
);

CREATE TABLE orders (
    order_id     SERIAL PRIMARY KEY,
    customer_id  INT REFERENCES customers(customer_id),
    order_date   TIMESTAMP,
    status       VARCHAR(20) CHECK (status IN ('completed','returned','pending')),
    total_amount NUMERIC(10,2)
);

CREATE TABLE order_items (
    item_id      SERIAL PRIMARY KEY,
    order_id     INT REFERENCES orders(order_id),
    product_id   INT REFERENCES products(product_id),
    quantity     INT,
    unit_price   NUMERIC(10,2)
);

CREATE TABLE events (
    event_id     SERIAL PRIMARY KEY,
    customer_id  INT REFERENCES customers(customer_id),
    event_type   VARCHAR(40),
    event_ts     TIMESTAMP,
    metadata     JSONB
);

CREATE TABLE payments (
    payment_id      SERIAL PRIMARY KEY,
    order_id        INT REFERENCES orders(order_id),
    payment_method  VARCHAR(30),
    payment_status  VARCHAR(20) CHECK (payment_status IN ('captured','failed','refunded')),
    amount          NUMERIC(10,2),
    paid_at         TIMESTAMP
);

CREATE TABLE shipments (
    shipment_id      SERIAL PRIMARY KEY,
    order_id         INT REFERENCES orders(order_id),
    carrier          VARCHAR(40),
    shipment_status  VARCHAR(20) CHECK (shipment_status IN ('pending','shipped','delivered','returned')),
    shipped_at       TIMESTAMP,
    delivered_at     TIMESTAMP
);

CREATE TABLE support_tickets (
    ticket_id     SERIAL PRIMARY KEY,
    customer_id   INT REFERENCES customers(customer_id),
    issue_type    VARCHAR(40),
    priority      VARCHAR(10) CHECK (priority IN ('low','medium','high')),
    status        VARCHAR(20) CHECK (status IN ('open','resolved')),
    created_at    TIMESTAMP,
    resolved_at   TIMESTAMP
);

-- Customers
INSERT INTO customers (first_name,last_name,email,country,age,signup_date,is_premium) VALUES
('Alice',  'Nguyen',   'alice@example.com',  'Pakistan',28,'2021-03-14',TRUE),
('Bob',    'Khan',     'bob@example.com',    'Pakistan',45,'2020-07-22',FALSE),
('Carol',  'Smith',    'carol@example.com',  'UAE',     34,'2022-01-05',TRUE),
('David',  'Ahmed',    'david@example.com',  'Pakistan',52,'2019-11-30',FALSE),
('Eva',    'Malik',    'eva@example.com',    'UK',      29,'2021-08-19',TRUE),
('Frank',  'Hassan',   'frank@example.com',  'Pakistan',23,'2023-02-11',FALSE),
('Grace',  'Chen',     'grace@example.com',  'USA',     40,'2020-05-03',TRUE),
('Hamza',  'Qureshi',  'hamza@example.com',  'Pakistan',31,'2022-09-17',FALSE),
('Irene',  'Johansson','irene@example.com',  'Sweden',  36,'2021-12-01',TRUE),
('Jasim',  'Al-Farsi', 'jasim@example.com',  'UAE',     48,'2020-03-28',FALSE),
('Kiran',  'Patel',    'kiran@example.com',  'India',   27,'2023-05-14',FALSE),
('Layla',  'Hussain',  'layla@example.com',  'Pakistan',33,'2021-06-07',TRUE),
('Marcus', 'Brown',    'marcus@example.com', 'USA',     55,'2019-08-15',TRUE),
('Nadia',  'Siddiqui', 'nadia@example.com',  'Pakistan',30,'2022-04-22',FALSE),
('Omar',   'Ibrahim',  'omar@example.com',   'Egypt',   41,'2020-10-09',TRUE);

-- Products
INSERT INTO products (name,category,unit_price,stock_qty) VALUES
('Wireless Headphones Pro',   'Electronics',  89.99, 230),
('Standing Desk Converter',   'Furniture',   149.99,  85),
('Mechanical Keyboard',       'Electronics',  74.99, 310),
('USB-C Hub 7-in-1',          'Electronics',  39.99, 450),
('Ergonomic Mouse',           'Electronics',  49.99, 280),
('Monitor Light Bar',         'Electronics',  29.99, 520),
('Notebook A5 Pack (5)',      'Stationery',    9.99, 900),
('Premium Coffee Blend 1kg',  'Food',         18.99, 340),
('Yoga Mat Anti-slip',        'Sports',       34.99, 190),
('Water Bottle 1L',           'Sports',       24.99, 670),
('Cable Management Kit',      'Accessories',  14.99, 810),
('Laptop Stand Aluminum',     'Accessories',  49.99, 175),
('Blue Light Glasses',        'Accessories',  22.99, 390),
('Portable Charger 20000mAh', 'Electronics',  59.99, 260),
('Desk Plant Succulent',      'Home',         12.99, 430);

-- Orders
INSERT INTO orders (customer_id,order_date,status,total_amount) VALUES
(1, '2024-01-03 09:15:00','completed',164.98),
(2, '2024-01-05 14:30:00','completed', 39.99),
(3, '2024-01-07 11:00:00','returned',  89.99),
(4, '2024-01-10 16:45:00','completed', 84.98),
(5, '2024-01-12 08:20:00','completed',199.98),
(1, '2024-01-15 13:10:00','completed', 29.99),
(6, '2024-01-18 10:05:00','pending',   74.99),
(7, '2024-01-20 15:55:00','completed',124.97),
(8, '2024-01-22 09:40:00','completed', 49.99),
(9, '2024-01-25 12:00:00','completed', 59.99),
(10,'2024-02-01 11:30:00','completed',149.99),
(11,'2024-02-03 14:15:00','returned',  34.99),
(12,'2024-02-05 09:00:00','completed', 89.98),
(13,'2024-02-08 16:20:00','completed',249.97),
(14,'2024-02-10 10:45:00','completed', 22.99),
(15,'2024-02-12 13:30:00','completed',174.98),
(1, '2024-02-15 08:55:00','completed', 18.99),
(3, '2024-02-18 15:10:00','completed', 49.99),
(5, '2024-02-20 11:25:00','completed',119.98),
(7, '2024-02-22 14:00:00','completed', 39.99);

-- Order items
INSERT INTO order_items (order_id,product_id,quantity,unit_price) VALUES
(1,1,1,89.99),(1,3,1,74.99),
(2,4,1,39.99),
(3,1,1,89.99),
(4,5,1,49.99),(4,7,2,9.99),(4,6,1,29.99),
(5,2,1,149.99),(5,5,1,49.99),
(6,6,1,29.99),
(7,3,1,74.99),
(8,8,2,18.99),(8,10,1,24.99),(8,11,1,14.99),(8,7,1,9.99),
(9,5,1,49.99),
(10,14,1,59.99),
(11,9,1,34.99),
(12,1,1,89.99),
(13,2,1,149.99),(13,4,1,39.99),(13,14,1,59.99),
(14,13,1,22.99),
(15,2,1,149.99),(15,12,1,49.99),
(16,8,1,18.99),
(17,5,1,49.99),
(18,1,1,89.99),(18,6,1,29.99),
(19,4,1,39.99),
(20,4,1,39.99);

-- Events
INSERT INTO events (customer_id,event_type,event_ts,metadata) VALUES
(1,'page_view',    '2024-01-02 08:10:00','{"page":"headphones"}'),
(1,'add_to_cart',  '2024-01-02 08:12:00','{"product_id":1}'),
(1,'checkout',     '2024-01-03 09:14:00','{"order_id":1}'),
(2,'page_view',    '2024-01-04 14:00:00','{"page":"usb-hubs"}'),
(2,'checkout',     '2024-01-05 14:29:00','{"order_id":2}'),
(3,'page_view',    '2024-01-06 10:50:00','{"page":"headphones"}'),
(3,'checkout',     '2024-01-07 10:59:00','{"order_id":3}'),
(3,'support_ticket','2024-01-09 09:00:00','{"reason":"return_request","order_id":3}'),
(4,'page_view',    '2024-01-09 16:30:00','{"page":"mice"}'),
(4,'checkout',     '2024-01-10 16:44:00','{"order_id":4}'),
(5,'page_view',    '2024-01-11 08:00:00','{"page":"desks"}'),
(5,'checkout',     '2024-01-12 08:19:00','{"order_id":5}'),
(6,'page_view',    '2024-01-17 09:55:00','{"page":"keyboards"}'),
(6,'add_to_cart',  '2024-01-17 10:00:00','{"product_id":3}'),
(7,'page_view',    '2024-01-19 15:40:00','{"page":"coffee"}'),
(7,'checkout',     '2024-01-20 15:54:00','{"order_id":8}'),
(8,'checkout',     '2024-01-22 09:39:00','{"order_id":9}'),
(9,'page_view',    '2024-01-24 11:45:00','{"page":"chargers"}'),
(9,'checkout',     '2024-01-25 11:59:00','{"order_id":10}'),
(13,'page_view',   '2024-02-07 10:00:00','{"page":"premium"}'),
(13,'checkout',    '2024-02-08 16:19:00','{"order_id":13}');

-- Payments
INSERT INTO payments (order_id,payment_method,payment_status,amount,paid_at) VALUES
(1,'card','captured',164.98,'2024-01-03 09:15:10'),
(2,'wallet','captured',39.99,'2024-01-05 14:30:12'),
(3,'card','refunded',89.99,'2024-01-08 09:00:00'),
(4,'bank_transfer','captured',84.98,'2024-01-10 16:46:00'),
(5,'card','captured',199.98,'2024-01-12 08:21:00'),
(6,'card','captured',29.99,'2024-01-15 13:11:00'),
(7,'card','failed',74.99,'2024-01-18 10:06:00'),
(8,'wallet','captured',124.97,'2024-01-20 15:56:00'),
(9,'card','captured',49.99,'2024-01-22 09:41:00'),
(10,'card','captured',59.99,'2024-01-25 12:01:00'),
(11,'bank_transfer','captured',149.99,'2024-02-01 11:31:00'),
(12,'card','refunded',34.99,'2024-02-04 12:00:00'),
(13,'card','captured',89.98,'2024-02-05 09:01:00'),
(14,'card','captured',249.97,'2024-02-08 16:21:00'),
(15,'wallet','captured',22.99,'2024-02-10 10:46:00'),
(16,'card','captured',174.98,'2024-02-12 13:31:00'),
(17,'card','captured',18.99,'2024-02-15 08:56:00'),
(18,'card','captured',49.99,'2024-02-18 15:11:00'),
(19,'wallet','captured',119.98,'2024-02-20 11:26:00'),
(20,'card','captured',39.99,'2024-02-22 14:01:00');

-- Shipments
INSERT INTO shipments (order_id,carrier,shipment_status,shipped_at,delivered_at) VALUES
(1,'DHL','delivered','2024-01-03 18:00:00','2024-01-05 12:00:00'),
(2,'Leopards','delivered','2024-01-06 08:00:00','2024-01-07 13:00:00'),
(3,'DHL','returned','2024-01-07 18:00:00','2024-01-10 15:00:00'),
(4,'TCS','delivered','2024-01-11 09:00:00','2024-01-12 16:00:00'),
(5,'DHL','delivered','2024-01-13 12:00:00','2024-01-15 18:30:00'),
(6,'Bykea','delivered','2024-01-15 18:00:00','2024-01-15 21:00:00'),
(7,'TCS','pending',NULL,NULL),
(8,'DHL','delivered','2024-01-21 09:00:00','2024-01-23 11:30:00'),
(9,'Bykea','delivered','2024-01-22 15:00:00','2024-01-22 19:00:00'),
(10,'DHL','delivered','2024-01-26 10:00:00','2024-01-28 14:00:00'),
(11,'TCS','delivered','2024-02-02 09:30:00','2024-02-05 12:30:00'),
(12,'DHL','returned','2024-02-03 10:00:00','2024-02-06 17:00:00'),
(13,'DHL','delivered','2024-02-05 17:00:00','2024-02-07 10:00:00'),
(14,'Leopards','delivered','2024-02-09 10:00:00','2024-02-10 13:00:00'),
(15,'Bykea','delivered','2024-02-10 14:00:00','2024-02-10 18:00:00'),
(16,'DHL','delivered','2024-02-13 09:00:00','2024-02-15 12:00:00'),
(17,'Bykea','delivered','2024-02-15 13:00:00','2024-02-15 17:00:00'),
(18,'DHL','delivered','2024-02-19 09:00:00','2024-02-20 14:00:00'),
(19,'Leopards','delivered','2024-02-21 08:30:00','2024-02-22 11:00:00'),
(20,'Bykea','delivered','2024-02-22 17:00:00','2024-02-22 20:00:00');

-- Support tickets
INSERT INTO support_tickets (customer_id,issue_type,priority,status,created_at,resolved_at) VALUES
(3,'return_request','medium','resolved','2024-01-09 09:00:00','2024-01-10 14:00:00'),
(6,'payment_failure','high','open','2024-01-18 10:20:00',NULL),
(8,'shipping_delay','low','resolved','2024-01-24 11:00:00','2024-01-25 10:30:00'),
(11,'refund_status','medium','resolved','2024-02-04 12:30:00','2024-02-06 13:00:00'),
(13,'bulk_order_help','low','resolved','2024-02-09 09:00:00','2024-02-09 12:00:00'),
(14,'product_question','low','resolved','2024-02-10 12:00:00','2024-02-10 13:30:00'),
(15,'shipment_tracking','medium','resolved','2024-02-13 10:00:00','2024-02-13 11:15:00');

-- Analyst views
CREATE VIEW customer_summary AS
SELECT c.customer_id,
       c.first_name||' '||c.last_name AS full_name,
       c.country, c.age, c.is_premium,
       COUNT(DISTINCT o.order_id) AS total_orders,
       COALESCE(SUM(o.total_amount) FILTER (WHERE o.status='completed'),0) AS total_spend,
       MAX(o.order_date) AS last_order_date,
       COUNT(e.event_id) FILTER (WHERE e.event_type='support_ticket') AS support_tickets
FROM customers c
LEFT JOIN orders o ON c.customer_id=o.customer_id
LEFT JOIN events e ON c.customer_id=e.customer_id
GROUP BY c.customer_id,c.first_name,c.last_name,c.country,c.age,c.is_premium;

CREATE VIEW product_performance AS
SELECT p.product_id, p.name, p.category,
       COUNT(oi.item_id) AS times_ordered,
       SUM(oi.quantity) AS units_sold,
       SUM(oi.quantity*oi.unit_price) AS revenue
FROM products p
LEFT JOIN order_items oi ON p.product_id=oi.product_id
GROUP BY p.product_id,p.name,p.category;

CREATE VIEW order_ops_overview AS
SELECT
    o.order_id,
    o.customer_id,
    o.status AS order_status,
    p.payment_status,
    s.shipment_status,
    o.total_amount,
    o.order_date
FROM orders o
LEFT JOIN payments p ON o.order_id = p.order_id
LEFT JOIN shipments s ON o.order_id = s.order_id;
