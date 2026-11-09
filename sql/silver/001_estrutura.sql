-- Executar somente pelo orquestrador silver.py: ele verifica o destino e abre a transação.
DO $guard$
BEGIN
 IF current_database() IS DISTINCT FROM current_setting('olist.expected_database', true)
    OR current_setting('server_encoding') <> 'UTF8'
    OR current_setting('server_version_num')::integer < 140000 THEN
   RAISE EXCEPTION 'Destino ou servidor incompatível';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_database d WHERE d.datname=current_database()
     AND pg_get_userbyid(d.datdba)=current_user
     AND shobj_description(d.oid,'pg_database')='inteligencia_receita:exclusive:v1') THEN
   RAISE EXCEPTION 'Exclusividade do projeto não comprovada';
 END IF;
 IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname !~ '^pg_'
     AND nspname NOT IN ('information_schema','public','silver'))
 OR EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
     WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
       AND NOT (n.nspname='silver' AND c.relname IN ('olist_customers_dataset','olist_customers_dataset_pkey','olist_geolocation_dataset','olist_geolocation_dataset_pkey','olist_orders_dataset','olist_orders_dataset_pkey','olist_order_items_dataset','olist_order_items_dataset_pkey','olist_order_payments_dataset','olist_order_payments_dataset_pkey','olist_order_reviews_dataset','olist_order_reviews_dataset_pkey','olist_products_dataset','olist_products_dataset_pkey','olist_sellers_dataset','olist_sellers_dataset_pkey','product_category_name_translation','product_category_name_translation_pkey') AND c.relkind IN ('r','i')))
 OR EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
     WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema')
 OR EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
     WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
       AND t.typrelid=0 AND t.typelem=0)
 OR EXISTS (SELECT 1 FROM pg_extension WHERE extname <> 'plpgsql')
 OR EXISTS (SELECT 1 FROM pg_event_trigger) THEN
   RAISE EXCEPTION 'Objetos externos encontrados; operação recusada';
 END IF;
 IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname='silver' AND
     (obj_description(oid,'pg_namespace') IS DISTINCT FROM 'inteligencia_receita:silver:v1'
       OR pg_get_userbyid(nspowner) <> current_user)) THEN
   RAISE EXCEPTION 'Schema silver sem identificação exclusiva do projeto';
 END IF;
 IF EXISTS (SELECT 1 FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
      JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='silver' AND NOT t.tgisinternal)
 OR EXISTS (SELECT 1 FROM pg_inherits i JOIN pg_class c ON c.oid=i.inhrelid
      JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='silver')
 OR EXISTS (SELECT 1 FROM pg_rewrite r JOIN pg_class c ON c.oid=r.ev_class
      JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='silver') THEN
   RAISE EXCEPTION 'Triggers ou regras não previstos';
 END IF;

 IF to_regclass('silver.olist_customers_dataset') IS NOT NULL THEN
   IF NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.oid=to_regclass('silver.olist_customers_dataset')
       AND c.relkind='r' AND NOT c.relispartition AND NOT c.relrowsecurity
       AND pg_get_userbyid(c.relowner)=current_user
       AND obj_description(c.oid,'pg_class')='inteligencia_receita:silver:v1:customers:f64f3cc5ec4895e538377636ba26f05c325364f10f76027d42374fc2c5b290db')
   OR (SELECT jsonb_agg(jsonb_build_object('name',a.attname,'type',format_type(a.atttypid,a.atttypmod),
               'required',a.attnotnull) ORDER BY a.attnum) FROM pg_attribute a
         WHERE a.attrelid=to_regclass('silver.olist_customers_dataset') AND a.attnum>0 AND NOT a.attisdropped)
       IS DISTINCT FROM '[{"name": "customer_id", "type": "text", "required": false}, {"name": "customer_unique_id", "type": "text", "required": false}, {"name": "customer_zip_code_prefix", "type": "text", "required": false}, {"name": "customer_city", "type": "text", "required": false}, {"name": "customer_state", "type": "text", "required": false}, {"name": "_source_file", "type": "text", "required": true}, {"name": "_source_sha256", "type": "text", "required": true}, {"name": "_source_row", "type": "bigint", "required": true}, {"name": "_raw_record", "type": "jsonb", "required": true}, {"name": "_conversion_errors", "type": "jsonb", "required": true}]'::jsonb
   OR EXISTS (SELECT 1 FROM pg_attrdef WHERE adrelid=to_regclass('silver.olist_customers_dataset'))
   OR EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid=to_regclass('silver.olist_customers_dataset')
       AND a.attnum>0 AND NOT a.attisdropped AND a.atttypid='text'::regtype
       AND a.attname NOT LIKE '\_%' ESCAPE '\' AND a.attcollation <> '"C"'::regcollation)
   OR (SELECT count(*) FROM pg_constraint WHERE conrelid=to_regclass('silver.olist_customers_dataset') AND contype <> 'n') <> 1
   OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('silver.olist_customers_dataset')
       AND contype='p' AND pg_get_constraintdef(oid)='PRIMARY KEY (_source_row)') THEN
     RAISE EXCEPTION 'Tabela existente incompatível: olist_customers_dataset';
   END IF;
 END IF;

 IF to_regclass('silver.olist_geolocation_dataset') IS NOT NULL THEN
   IF NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.oid=to_regclass('silver.olist_geolocation_dataset')
       AND c.relkind='r' AND NOT c.relispartition AND NOT c.relrowsecurity
       AND pg_get_userbyid(c.relowner)=current_user
       AND obj_description(c.oid,'pg_class')='inteligencia_receita:silver:v1:geolocation:ef221831e7217a146eef347aec0af236196b78356e67030f059d5da67cd22269')
   OR (SELECT jsonb_agg(jsonb_build_object('name',a.attname,'type',format_type(a.atttypid,a.atttypmod),
               'required',a.attnotnull) ORDER BY a.attnum) FROM pg_attribute a
         WHERE a.attrelid=to_regclass('silver.olist_geolocation_dataset') AND a.attnum>0 AND NOT a.attisdropped)
       IS DISTINCT FROM '[{"name": "geolocation_zip_code_prefix", "type": "text", "required": false}, {"name": "geolocation_lat", "type": "numeric", "required": false}, {"name": "geolocation_lng", "type": "numeric", "required": false}, {"name": "geolocation_city", "type": "text", "required": false}, {"name": "geolocation_state", "type": "text", "required": false}, {"name": "_source_file", "type": "text", "required": true}, {"name": "_source_sha256", "type": "text", "required": true}, {"name": "_source_row", "type": "bigint", "required": true}, {"name": "_raw_record", "type": "jsonb", "required": true}, {"name": "_conversion_errors", "type": "jsonb", "required": true}]'::jsonb
   OR EXISTS (SELECT 1 FROM pg_attrdef WHERE adrelid=to_regclass('silver.olist_geolocation_dataset'))
   OR EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid=to_regclass('silver.olist_geolocation_dataset')
       AND a.attnum>0 AND NOT a.attisdropped AND a.atttypid='text'::regtype
       AND a.attname NOT LIKE '\_%' ESCAPE '\' AND a.attcollation <> '"C"'::regcollation)
   OR (SELECT count(*) FROM pg_constraint WHERE conrelid=to_regclass('silver.olist_geolocation_dataset') AND contype <> 'n') <> 1
   OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('silver.olist_geolocation_dataset')
       AND contype='p' AND pg_get_constraintdef(oid)='PRIMARY KEY (_source_row)') THEN
     RAISE EXCEPTION 'Tabela existente incompatível: olist_geolocation_dataset';
   END IF;
 END IF;

 IF to_regclass('silver.olist_orders_dataset') IS NOT NULL THEN
   IF NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.oid=to_regclass('silver.olist_orders_dataset')
       AND c.relkind='r' AND NOT c.relispartition AND NOT c.relrowsecurity
       AND pg_get_userbyid(c.relowner)=current_user
       AND obj_description(c.oid,'pg_class')='inteligencia_receita:silver:v1:orders:e6fcba13e45a0fb856118028a8d5bcb412bd3abfdb7dc827df357f31f8285fec')
   OR (SELECT jsonb_agg(jsonb_build_object('name',a.attname,'type',format_type(a.atttypid,a.atttypmod),
               'required',a.attnotnull) ORDER BY a.attnum) FROM pg_attribute a
         WHERE a.attrelid=to_regclass('silver.olist_orders_dataset') AND a.attnum>0 AND NOT a.attisdropped)
       IS DISTINCT FROM '[{"name": "order_id", "type": "text", "required": false}, {"name": "customer_id", "type": "text", "required": false}, {"name": "order_status", "type": "text", "required": false}, {"name": "order_purchase_timestamp", "type": "timestamp without time zone", "required": false}, {"name": "order_approved_at", "type": "timestamp without time zone", "required": false}, {"name": "order_delivered_carrier_date", "type": "timestamp without time zone", "required": false}, {"name": "order_delivered_customer_date", "type": "timestamp without time zone", "required": false}, {"name": "order_estimated_delivery_date", "type": "timestamp without time zone", "required": false}, {"name": "_source_file", "type": "text", "required": true}, {"name": "_source_sha256", "type": "text", "required": true}, {"name": "_source_row", "type": "bigint", "required": true}, {"name": "_raw_record", "type": "jsonb", "required": true}, {"name": "_conversion_errors", "type": "jsonb", "required": true}]'::jsonb
   OR EXISTS (SELECT 1 FROM pg_attrdef WHERE adrelid=to_regclass('silver.olist_orders_dataset'))
   OR EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid=to_regclass('silver.olist_orders_dataset')
       AND a.attnum>0 AND NOT a.attisdropped AND a.atttypid='text'::regtype
       AND a.attname NOT LIKE '\_%' ESCAPE '\' AND a.attcollation <> '"C"'::regcollation)
   OR (SELECT count(*) FROM pg_constraint WHERE conrelid=to_regclass('silver.olist_orders_dataset') AND contype <> 'n') <> 1
   OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('silver.olist_orders_dataset')
       AND contype='p' AND pg_get_constraintdef(oid)='PRIMARY KEY (_source_row)') THEN
     RAISE EXCEPTION 'Tabela existente incompatível: olist_orders_dataset';
   END IF;
 END IF;

 IF to_regclass('silver.olist_order_items_dataset') IS NOT NULL THEN
   IF NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.oid=to_regclass('silver.olist_order_items_dataset')
       AND c.relkind='r' AND NOT c.relispartition AND NOT c.relrowsecurity
       AND pg_get_userbyid(c.relowner)=current_user
       AND obj_description(c.oid,'pg_class')='inteligencia_receita:silver:v1:items:846808c8fac4fcdabf8fcc663fa3faa8dcb2e639c9566c2ba256d052e08f2ad0')
   OR (SELECT jsonb_agg(jsonb_build_object('name',a.attname,'type',format_type(a.atttypid,a.atttypmod),
               'required',a.attnotnull) ORDER BY a.attnum) FROM pg_attribute a
         WHERE a.attrelid=to_regclass('silver.olist_order_items_dataset') AND a.attnum>0 AND NOT a.attisdropped)
       IS DISTINCT FROM '[{"name": "order_id", "type": "text", "required": false}, {"name": "order_item_id", "type": "text", "required": false}, {"name": "product_id", "type": "text", "required": false}, {"name": "seller_id", "type": "text", "required": false}, {"name": "shipping_limit_date", "type": "timestamp without time zone", "required": false}, {"name": "price", "type": "numeric", "required": false}, {"name": "freight_value", "type": "numeric", "required": false}, {"name": "_source_file", "type": "text", "required": true}, {"name": "_source_sha256", "type": "text", "required": true}, {"name": "_source_row", "type": "bigint", "required": true}, {"name": "_raw_record", "type": "jsonb", "required": true}, {"name": "_conversion_errors", "type": "jsonb", "required": true}]'::jsonb
   OR EXISTS (SELECT 1 FROM pg_attrdef WHERE adrelid=to_regclass('silver.olist_order_items_dataset'))
   OR EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid=to_regclass('silver.olist_order_items_dataset')
       AND a.attnum>0 AND NOT a.attisdropped AND a.atttypid='text'::regtype
       AND a.attname NOT LIKE '\_%' ESCAPE '\' AND a.attcollation <> '"C"'::regcollation)
   OR (SELECT count(*) FROM pg_constraint WHERE conrelid=to_regclass('silver.olist_order_items_dataset') AND contype <> 'n') <> 1
   OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('silver.olist_order_items_dataset')
       AND contype='p' AND pg_get_constraintdef(oid)='PRIMARY KEY (_source_row)') THEN
     RAISE EXCEPTION 'Tabela existente incompatível: olist_order_items_dataset';
   END IF;
 END IF;

 IF to_regclass('silver.olist_order_payments_dataset') IS NOT NULL THEN
   IF NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.oid=to_regclass('silver.olist_order_payments_dataset')
       AND c.relkind='r' AND NOT c.relispartition AND NOT c.relrowsecurity
       AND pg_get_userbyid(c.relowner)=current_user
       AND obj_description(c.oid,'pg_class')='inteligencia_receita:silver:v1:payments:fa521c255d319b597d1620b66fab84073694a0386625f831e49a172ac1648c82')
   OR (SELECT jsonb_agg(jsonb_build_object('name',a.attname,'type',format_type(a.atttypid,a.atttypmod),
               'required',a.attnotnull) ORDER BY a.attnum) FROM pg_attribute a
         WHERE a.attrelid=to_regclass('silver.olist_order_payments_dataset') AND a.attnum>0 AND NOT a.attisdropped)
       IS DISTINCT FROM '[{"name": "order_id", "type": "text", "required": false}, {"name": "payment_sequential", "type": "text", "required": false}, {"name": "payment_type", "type": "text", "required": false}, {"name": "payment_installments", "type": "numeric", "required": false}, {"name": "payment_value", "type": "numeric", "required": false}, {"name": "_source_file", "type": "text", "required": true}, {"name": "_source_sha256", "type": "text", "required": true}, {"name": "_source_row", "type": "bigint", "required": true}, {"name": "_raw_record", "type": "jsonb", "required": true}, {"name": "_conversion_errors", "type": "jsonb", "required": true}]'::jsonb
   OR EXISTS (SELECT 1 FROM pg_attrdef WHERE adrelid=to_regclass('silver.olist_order_payments_dataset'))
   OR EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid=to_regclass('silver.olist_order_payments_dataset')
       AND a.attnum>0 AND NOT a.attisdropped AND a.atttypid='text'::regtype
       AND a.attname NOT LIKE '\_%' ESCAPE '\' AND a.attcollation <> '"C"'::regcollation)
   OR (SELECT count(*) FROM pg_constraint WHERE conrelid=to_regclass('silver.olist_order_payments_dataset') AND contype <> 'n') <> 1
   OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('silver.olist_order_payments_dataset')
       AND contype='p' AND pg_get_constraintdef(oid)='PRIMARY KEY (_source_row)') THEN
     RAISE EXCEPTION 'Tabela existente incompatível: olist_order_payments_dataset';
   END IF;
 END IF;

 IF to_regclass('silver.olist_order_reviews_dataset') IS NOT NULL THEN
   IF NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.oid=to_regclass('silver.olist_order_reviews_dataset')
       AND c.relkind='r' AND NOT c.relispartition AND NOT c.relrowsecurity
       AND pg_get_userbyid(c.relowner)=current_user
       AND obj_description(c.oid,'pg_class')='inteligencia_receita:silver:v1:reviews:5fd3003f7af2ec41165390b7959ada5f0097955def4d0efba585f9f4caae39c2')
   OR (SELECT jsonb_agg(jsonb_build_object('name',a.attname,'type',format_type(a.atttypid,a.atttypmod),
               'required',a.attnotnull) ORDER BY a.attnum) FROM pg_attribute a
         WHERE a.attrelid=to_regclass('silver.olist_order_reviews_dataset') AND a.attnum>0 AND NOT a.attisdropped)
       IS DISTINCT FROM '[{"name": "review_id", "type": "text", "required": false}, {"name": "order_id", "type": "text", "required": false}, {"name": "review_score", "type": "numeric", "required": false}, {"name": "review_comment_title", "type": "text", "required": false}, {"name": "review_comment_message", "type": "text", "required": false}, {"name": "review_creation_date", "type": "timestamp without time zone", "required": false}, {"name": "review_answer_timestamp", "type": "timestamp without time zone", "required": false}, {"name": "_source_file", "type": "text", "required": true}, {"name": "_source_sha256", "type": "text", "required": true}, {"name": "_source_row", "type": "bigint", "required": true}, {"name": "_raw_record", "type": "jsonb", "required": true}, {"name": "_conversion_errors", "type": "jsonb", "required": true}]'::jsonb
   OR EXISTS (SELECT 1 FROM pg_attrdef WHERE adrelid=to_regclass('silver.olist_order_reviews_dataset'))
   OR EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid=to_regclass('silver.olist_order_reviews_dataset')
       AND a.attnum>0 AND NOT a.attisdropped AND a.atttypid='text'::regtype
       AND a.attname NOT LIKE '\_%' ESCAPE '\' AND a.attcollation <> '"C"'::regcollation)
   OR (SELECT count(*) FROM pg_constraint WHERE conrelid=to_regclass('silver.olist_order_reviews_dataset') AND contype <> 'n') <> 1
   OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('silver.olist_order_reviews_dataset')
       AND contype='p' AND pg_get_constraintdef(oid)='PRIMARY KEY (_source_row)') THEN
     RAISE EXCEPTION 'Tabela existente incompatível: olist_order_reviews_dataset';
   END IF;
 END IF;

 IF to_regclass('silver.olist_products_dataset') IS NOT NULL THEN
   IF NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.oid=to_regclass('silver.olist_products_dataset')
       AND c.relkind='r' AND NOT c.relispartition AND NOT c.relrowsecurity
       AND pg_get_userbyid(c.relowner)=current_user
       AND obj_description(c.oid,'pg_class')='inteligencia_receita:silver:v1:products:7dab8aaa86015b366621821a935698c76c5528a7ae3cae5bc584d578022664d6')
   OR (SELECT jsonb_agg(jsonb_build_object('name',a.attname,'type',format_type(a.atttypid,a.atttypmod),
               'required',a.attnotnull) ORDER BY a.attnum) FROM pg_attribute a
         WHERE a.attrelid=to_regclass('silver.olist_products_dataset') AND a.attnum>0 AND NOT a.attisdropped)
       IS DISTINCT FROM '[{"name": "product_id", "type": "text", "required": false}, {"name": "product_category_name", "type": "text", "required": false}, {"name": "product_name_lenght", "type": "numeric", "required": false}, {"name": "product_description_lenght", "type": "numeric", "required": false}, {"name": "product_photos_qty", "type": "numeric", "required": false}, {"name": "product_weight_g", "type": "numeric", "required": false}, {"name": "product_length_cm", "type": "numeric", "required": false}, {"name": "product_height_cm", "type": "numeric", "required": false}, {"name": "product_width_cm", "type": "numeric", "required": false}, {"name": "_source_file", "type": "text", "required": true}, {"name": "_source_sha256", "type": "text", "required": true}, {"name": "_source_row", "type": "bigint", "required": true}, {"name": "_raw_record", "type": "jsonb", "required": true}, {"name": "_conversion_errors", "type": "jsonb", "required": true}]'::jsonb
   OR EXISTS (SELECT 1 FROM pg_attrdef WHERE adrelid=to_regclass('silver.olist_products_dataset'))
   OR EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid=to_regclass('silver.olist_products_dataset')
       AND a.attnum>0 AND NOT a.attisdropped AND a.atttypid='text'::regtype
       AND a.attname NOT LIKE '\_%' ESCAPE '\' AND a.attcollation <> '"C"'::regcollation)
   OR (SELECT count(*) FROM pg_constraint WHERE conrelid=to_regclass('silver.olist_products_dataset') AND contype <> 'n') <> 1
   OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('silver.olist_products_dataset')
       AND contype='p' AND pg_get_constraintdef(oid)='PRIMARY KEY (_source_row)') THEN
     RAISE EXCEPTION 'Tabela existente incompatível: olist_products_dataset';
   END IF;
 END IF;

 IF to_regclass('silver.olist_sellers_dataset') IS NOT NULL THEN
   IF NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.oid=to_regclass('silver.olist_sellers_dataset')
       AND c.relkind='r' AND NOT c.relispartition AND NOT c.relrowsecurity
       AND pg_get_userbyid(c.relowner)=current_user
       AND obj_description(c.oid,'pg_class')='inteligencia_receita:silver:v1:sellers:bc583c1588f46ebc26f8a2ba11143dd379e0c0a68438a551509e2da0f20a9741')
   OR (SELECT jsonb_agg(jsonb_build_object('name',a.attname,'type',format_type(a.atttypid,a.atttypmod),
               'required',a.attnotnull) ORDER BY a.attnum) FROM pg_attribute a
         WHERE a.attrelid=to_regclass('silver.olist_sellers_dataset') AND a.attnum>0 AND NOT a.attisdropped)
       IS DISTINCT FROM '[{"name": "seller_id", "type": "text", "required": false}, {"name": "seller_zip_code_prefix", "type": "text", "required": false}, {"name": "seller_city", "type": "text", "required": false}, {"name": "seller_state", "type": "text", "required": false}, {"name": "_source_file", "type": "text", "required": true}, {"name": "_source_sha256", "type": "text", "required": true}, {"name": "_source_row", "type": "bigint", "required": true}, {"name": "_raw_record", "type": "jsonb", "required": true}, {"name": "_conversion_errors", "type": "jsonb", "required": true}]'::jsonb
   OR EXISTS (SELECT 1 FROM pg_attrdef WHERE adrelid=to_regclass('silver.olist_sellers_dataset'))
   OR EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid=to_regclass('silver.olist_sellers_dataset')
       AND a.attnum>0 AND NOT a.attisdropped AND a.atttypid='text'::regtype
       AND a.attname NOT LIKE '\_%' ESCAPE '\' AND a.attcollation <> '"C"'::regcollation)
   OR (SELECT count(*) FROM pg_constraint WHERE conrelid=to_regclass('silver.olist_sellers_dataset') AND contype <> 'n') <> 1
   OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('silver.olist_sellers_dataset')
       AND contype='p' AND pg_get_constraintdef(oid)='PRIMARY KEY (_source_row)') THEN
     RAISE EXCEPTION 'Tabela existente incompatível: olist_sellers_dataset';
   END IF;
 END IF;

 IF to_regclass('silver.product_category_name_translation') IS NOT NULL THEN
   IF NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.oid=to_regclass('silver.product_category_name_translation')
       AND c.relkind='r' AND NOT c.relispartition AND NOT c.relrowsecurity
       AND pg_get_userbyid(c.relowner)=current_user
       AND obj_description(c.oid,'pg_class')='inteligencia_receita:silver:v1:translation:6636a48b6a82b7d62b2317a6a1d3e2efec5f78587ed34077f3d27f2ad852db02')
   OR (SELECT jsonb_agg(jsonb_build_object('name',a.attname,'type',format_type(a.atttypid,a.atttypmod),
               'required',a.attnotnull) ORDER BY a.attnum) FROM pg_attribute a
         WHERE a.attrelid=to_regclass('silver.product_category_name_translation') AND a.attnum>0 AND NOT a.attisdropped)
       IS DISTINCT FROM '[{"name": "product_category_name", "type": "text", "required": false}, {"name": "product_category_name_english", "type": "text", "required": false}, {"name": "_source_file", "type": "text", "required": true}, {"name": "_source_sha256", "type": "text", "required": true}, {"name": "_source_row", "type": "bigint", "required": true}, {"name": "_raw_record", "type": "jsonb", "required": true}, {"name": "_conversion_errors", "type": "jsonb", "required": true}]'::jsonb
   OR EXISTS (SELECT 1 FROM pg_attrdef WHERE adrelid=to_regclass('silver.product_category_name_translation'))
   OR EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid=to_regclass('silver.product_category_name_translation')
       AND a.attnum>0 AND NOT a.attisdropped AND a.atttypid='text'::regtype
       AND a.attname NOT LIKE '\_%' ESCAPE '\' AND a.attcollation <> '"C"'::regcollation)
   OR (SELECT count(*) FROM pg_constraint WHERE conrelid=to_regclass('silver.product_category_name_translation') AND contype <> 'n') <> 1
   OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('silver.product_category_name_translation')
       AND contype='p' AND pg_get_constraintdef(oid)='PRIMARY KEY (_source_row)') THEN
     RAISE EXCEPTION 'Tabela existente incompatível: product_category_name_translation';
   END IF;
 END IF;
END $guard$;
CREATE SCHEMA IF NOT EXISTS silver;
COMMENT ON SCHEMA silver IS 'inteligencia_receita:silver:v1';
CREATE TABLE IF NOT EXISTS silver."olist_customers_dataset" (
  "customer_id" text COLLATE "C",
  "customer_unique_id" text COLLATE "C",
  "customer_zip_code_prefix" text COLLATE "C",
  "customer_city" text COLLATE "C",
  "customer_state" text COLLATE "C",
  "_source_file" text NOT NULL,
  "_source_sha256" text NOT NULL,
  "_source_row" bigint NOT NULL PRIMARY KEY,
  "_raw_record" jsonb NOT NULL,
  "_conversion_errors" jsonb NOT NULL
);
COMMENT ON TABLE silver."olist_customers_dataset" IS 'inteligencia_receita:silver:v1:customers:f64f3cc5ec4895e538377636ba26f05c325364f10f76027d42374fc2c5b290db';
CREATE TABLE IF NOT EXISTS silver."olist_geolocation_dataset" (
  "geolocation_zip_code_prefix" text COLLATE "C",
  "geolocation_lat" numeric,
  "geolocation_lng" numeric,
  "geolocation_city" text COLLATE "C",
  "geolocation_state" text COLLATE "C",
  "_source_file" text NOT NULL,
  "_source_sha256" text NOT NULL,
  "_source_row" bigint NOT NULL PRIMARY KEY,
  "_raw_record" jsonb NOT NULL,
  "_conversion_errors" jsonb NOT NULL
);
COMMENT ON TABLE silver."olist_geolocation_dataset" IS 'inteligencia_receita:silver:v1:geolocation:ef221831e7217a146eef347aec0af236196b78356e67030f059d5da67cd22269';
CREATE TABLE IF NOT EXISTS silver."olist_orders_dataset" (
  "order_id" text COLLATE "C",
  "customer_id" text COLLATE "C",
  "order_status" text COLLATE "C",
  "order_purchase_timestamp" timestamp without time zone,
  "order_approved_at" timestamp without time zone,
  "order_delivered_carrier_date" timestamp without time zone,
  "order_delivered_customer_date" timestamp without time zone,
  "order_estimated_delivery_date" timestamp without time zone,
  "_source_file" text NOT NULL,
  "_source_sha256" text NOT NULL,
  "_source_row" bigint NOT NULL PRIMARY KEY,
  "_raw_record" jsonb NOT NULL,
  "_conversion_errors" jsonb NOT NULL
);
COMMENT ON TABLE silver."olist_orders_dataset" IS 'inteligencia_receita:silver:v1:orders:e6fcba13e45a0fb856118028a8d5bcb412bd3abfdb7dc827df357f31f8285fec';
CREATE TABLE IF NOT EXISTS silver."olist_order_items_dataset" (
  "order_id" text COLLATE "C",
  "order_item_id" text COLLATE "C",
  "product_id" text COLLATE "C",
  "seller_id" text COLLATE "C",
  "shipping_limit_date" timestamp without time zone,
  "price" numeric,
  "freight_value" numeric,
  "_source_file" text NOT NULL,
  "_source_sha256" text NOT NULL,
  "_source_row" bigint NOT NULL PRIMARY KEY,
  "_raw_record" jsonb NOT NULL,
  "_conversion_errors" jsonb NOT NULL
);
COMMENT ON TABLE silver."olist_order_items_dataset" IS 'inteligencia_receita:silver:v1:items:846808c8fac4fcdabf8fcc663fa3faa8dcb2e639c9566c2ba256d052e08f2ad0';
CREATE TABLE IF NOT EXISTS silver."olist_order_payments_dataset" (
  "order_id" text COLLATE "C",
  "payment_sequential" text COLLATE "C",
  "payment_type" text COLLATE "C",
  "payment_installments" numeric,
  "payment_value" numeric,
  "_source_file" text NOT NULL,
  "_source_sha256" text NOT NULL,
  "_source_row" bigint NOT NULL PRIMARY KEY,
  "_raw_record" jsonb NOT NULL,
  "_conversion_errors" jsonb NOT NULL
);
COMMENT ON TABLE silver."olist_order_payments_dataset" IS 'inteligencia_receita:silver:v1:payments:fa521c255d319b597d1620b66fab84073694a0386625f831e49a172ac1648c82';
CREATE TABLE IF NOT EXISTS silver."olist_order_reviews_dataset" (
  "review_id" text COLLATE "C",
  "order_id" text COLLATE "C",
  "review_score" numeric,
  "review_comment_title" text COLLATE "C",
  "review_comment_message" text COLLATE "C",
  "review_creation_date" timestamp without time zone,
  "review_answer_timestamp" timestamp without time zone,
  "_source_file" text NOT NULL,
  "_source_sha256" text NOT NULL,
  "_source_row" bigint NOT NULL PRIMARY KEY,
  "_raw_record" jsonb NOT NULL,
  "_conversion_errors" jsonb NOT NULL
);
COMMENT ON TABLE silver."olist_order_reviews_dataset" IS 'inteligencia_receita:silver:v1:reviews:5fd3003f7af2ec41165390b7959ada5f0097955def4d0efba585f9f4caae39c2';
CREATE TABLE IF NOT EXISTS silver."olist_products_dataset" (
  "product_id" text COLLATE "C",
  "product_category_name" text COLLATE "C",
  "product_name_lenght" numeric,
  "product_description_lenght" numeric,
  "product_photos_qty" numeric,
  "product_weight_g" numeric,
  "product_length_cm" numeric,
  "product_height_cm" numeric,
  "product_width_cm" numeric,
  "_source_file" text NOT NULL,
  "_source_sha256" text NOT NULL,
  "_source_row" bigint NOT NULL PRIMARY KEY,
  "_raw_record" jsonb NOT NULL,
  "_conversion_errors" jsonb NOT NULL
);
COMMENT ON TABLE silver."olist_products_dataset" IS 'inteligencia_receita:silver:v1:products:7dab8aaa86015b366621821a935698c76c5528a7ae3cae5bc584d578022664d6';
CREATE TABLE IF NOT EXISTS silver."olist_sellers_dataset" (
  "seller_id" text COLLATE "C",
  "seller_zip_code_prefix" text COLLATE "C",
  "seller_city" text COLLATE "C",
  "seller_state" text COLLATE "C",
  "_source_file" text NOT NULL,
  "_source_sha256" text NOT NULL,
  "_source_row" bigint NOT NULL PRIMARY KEY,
  "_raw_record" jsonb NOT NULL,
  "_conversion_errors" jsonb NOT NULL
);
COMMENT ON TABLE silver."olist_sellers_dataset" IS 'inteligencia_receita:silver:v1:sellers:bc583c1588f46ebc26f8a2ba11143dd379e0c0a68438a551509e2da0f20a9741';
CREATE TABLE IF NOT EXISTS silver."product_category_name_translation" (
  "product_category_name" text COLLATE "C",
  "product_category_name_english" text COLLATE "C",
  "_source_file" text NOT NULL,
  "_source_sha256" text NOT NULL,
  "_source_row" bigint NOT NULL PRIMARY KEY,
  "_raw_record" jsonb NOT NULL,
  "_conversion_errors" jsonb NOT NULL
);
COMMENT ON TABLE silver."product_category_name_translation" IS 'inteligencia_receita:silver:v1:translation:6636a48b6a82b7d62b2317a6a1d3e2efec5f78587ed34077f3d27f2ad852db02';
