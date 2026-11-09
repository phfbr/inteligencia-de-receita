-- Consultas de qualidade; nenhuma transformação ou exclusão.
SELECT json_build_object('table','olist_customers_dataset','rows',count(*),'conversion_error_rows',count(*) FILTER (WHERE _conversion_errors <> '{}'::jsonb)) FROM silver."olist_customers_dataset";
SELECT json_build_object('table','olist_geolocation_dataset','rows',count(*),'conversion_error_rows',count(*) FILTER (WHERE _conversion_errors <> '{}'::jsonb)) FROM silver."olist_geolocation_dataset";
SELECT json_build_object('table','olist_orders_dataset','rows',count(*),'conversion_error_rows',count(*) FILTER (WHERE _conversion_errors <> '{}'::jsonb)) FROM silver."olist_orders_dataset";
SELECT json_build_object('table','olist_order_items_dataset','rows',count(*),'conversion_error_rows',count(*) FILTER (WHERE _conversion_errors <> '{}'::jsonb)) FROM silver."olist_order_items_dataset";
SELECT json_build_object('table','olist_order_payments_dataset','rows',count(*),'conversion_error_rows',count(*) FILTER (WHERE _conversion_errors <> '{}'::jsonb)) FROM silver."olist_order_payments_dataset";
SELECT json_build_object('table','olist_order_reviews_dataset','rows',count(*),'conversion_error_rows',count(*) FILTER (WHERE _conversion_errors <> '{}'::jsonb)) FROM silver."olist_order_reviews_dataset";
SELECT json_build_object('table','olist_products_dataset','rows',count(*),'conversion_error_rows',count(*) FILTER (WHERE _conversion_errors <> '{}'::jsonb)) FROM silver."olist_products_dataset";
SELECT json_build_object('table','olist_sellers_dataset','rows',count(*),'conversion_error_rows',count(*) FILTER (WHERE _conversion_errors <> '{}'::jsonb)) FROM silver."olist_sellers_dataset";
SELECT json_build_object('table','product_category_name_translation','rows',count(*),'conversion_error_rows',count(*) FILTER (WHERE _conversion_errors <> '{}'::jsonb)) FROM silver."product_category_name_translation";
SELECT json_build_object('reference','orders.customer_id->customers.customer_id','orphans',count(*)) FROM silver."olist_orders_dataset" c WHERE c."customer_id" IS NOT NULL AND NOT EXISTS (SELECT 1 FROM silver."olist_customers_dataset" p WHERE p."customer_id"=c."customer_id");
SELECT json_build_object('reference','items.order_id->orders.order_id','orphans',count(*)) FROM silver."olist_order_items_dataset" c WHERE c."order_id" IS NOT NULL AND NOT EXISTS (SELECT 1 FROM silver."olist_orders_dataset" p WHERE p."order_id"=c."order_id");
SELECT json_build_object('reference','payments.order_id->orders.order_id','orphans',count(*)) FROM silver."olist_order_payments_dataset" c WHERE c."order_id" IS NOT NULL AND NOT EXISTS (SELECT 1 FROM silver."olist_orders_dataset" p WHERE p."order_id"=c."order_id");
SELECT json_build_object('reference','reviews.order_id->orders.order_id','orphans',count(*)) FROM silver."olist_order_reviews_dataset" c WHERE c."order_id" IS NOT NULL AND NOT EXISTS (SELECT 1 FROM silver."olist_orders_dataset" p WHERE p."order_id"=c."order_id");
SELECT json_build_object('reference','items.product_id->products.product_id','orphans',count(*)) FROM silver."olist_order_items_dataset" c WHERE c."product_id" IS NOT NULL AND NOT EXISTS (SELECT 1 FROM silver."olist_products_dataset" p WHERE p."product_id"=c."product_id");
SELECT json_build_object('reference','items.seller_id->sellers.seller_id','orphans',count(*)) FROM silver."olist_order_items_dataset" c WHERE c."seller_id" IS NOT NULL AND NOT EXISTS (SELECT 1 FROM silver."olist_sellers_dataset" p WHERE p."seller_id"=c."seller_id");
SELECT json_build_object('reference','products.product_category_name->translation.product_category_name','orphans',count(*)) FROM silver."olist_products_dataset" c WHERE c."product_category_name" IS NOT NULL AND NOT EXISTS (SELECT 1 FROM silver."product_category_name_translation" p WHERE p."product_category_name"=c."product_category_name");
WITH i AS (SELECT order_id,sum(price) price,sum(freight_value) freight
 FROM silver.olist_order_items_dataset GROUP BY order_id),
 p AS (SELECT order_id,sum(payment_value) payment FROM silver.olist_order_payments_dataset GROUP BY order_id)
SELECT json_build_object('reconciliation_compared',count(*),'over_one_cent',count(*) FILTER
 (WHERE abs(p.payment-i.price-i.freight)>0.01),'positive',count(*) FILTER
 (WHERE p.payment-i.price-i.freight>0.01),'negative',count(*) FILTER
 (WHERE p.payment-i.price-i.freight < -0.01))
FROM silver.olist_orders_dataset o JOIN i USING(order_id) JOIN p USING(order_id);
