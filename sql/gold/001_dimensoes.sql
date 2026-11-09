-- Executar via gold_dimensoes.py; validações e transação são obrigatórias.
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
     AND nspname NOT IN ('information_schema','public','silver','gold'))
 OR EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
     WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
       AND NOT ((n.nspname='silver' AND c.relname IN ('olist_customers_dataset','olist_customers_dataset_pkey','olist_geolocation_dataset','olist_geolocation_dataset_pkey','olist_orders_dataset','olist_orders_dataset_pkey','olist_order_items_dataset','olist_order_items_dataset_pkey','olist_order_payments_dataset','olist_order_payments_dataset_pkey','olist_order_reviews_dataset','olist_order_reviews_dataset_pkey','olist_products_dataset','olist_products_dataset_pkey','olist_sellers_dataset','olist_sellers_dataset_pkey','product_category_name_translation','product_category_name_translation_pkey') AND c.relkind IN ('r','i')) OR (n.nspname='gold' AND ((c.relkind='r' AND c.relname IN ('dim_clientes','dim_produtos','dim_vendedores','dim_calendario','dim_localizacao','dim_forma_pagamento')) OR (c.relkind='i' AND c.relname IN ('dim_clientes_pkey','dim_clientes_nk','dim_produtos_pkey','dim_produtos_nk','dim_vendedores_pkey','dim_vendedores_nk','dim_calendario_pkey','dim_calendario_nk','dim_localizacao_pkey','dim_localizacao_nk','dim_forma_pagamento_pkey','dim_forma_pagamento_nk'))))))
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
DO $gold_guard$ BEGIN
 IF current_database() <> 'inteligencia_receita_db' THEN RAISE EXCEPTION 'Banco fora do projeto'; END IF;
 IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname='gold' AND
  (obj_description(oid,'pg_namespace') IS DISTINCT FROM 'inteligencia_receita:gold_dimensoes:v1' OR pg_get_userbyid(nspowner)<>current_user))
 THEN RAISE EXCEPTION 'Schema gold preexistente não reconhecido'; END IF;
 IF EXISTS (SELECT 1 FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname='gold' AND NOT t.tgisinternal)
 OR EXISTS (SELECT 1 FROM pg_rewrite r JOIN pg_class c ON c.oid=r.ev_class JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='gold')
 OR EXISTS (SELECT 1 FROM pg_inherits i JOIN pg_class c ON c.oid=i.inhrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='gold')
 THEN RAISE EXCEPTION 'Comportamento não previsto na Gold'; END IF;

 IF to_regclass('gold.dim_clientes') IS NOT NULL THEN
  IF NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.oid=to_regclass('gold.dim_clientes') AND c.relkind='r'
   AND NOT c.relrowsecurity AND NOT c.relispartition AND pg_get_userbyid(c.relowner)=current_user
   AND obj_description(c.oid,'pg_class')='inteligencia_receita:gold_dimensoes:v1:cc484a45e7406a1c84f259137897c554e2c73012a8fc756b63cbb8b181ddb346')
  OR (SELECT jsonb_agg(jsonb_build_object('name',attname,'type',format_type(atttypid,atttypmod),'required',attnotnull) ORDER BY attnum)
   FROM pg_attribute WHERE attrelid=to_regclass('gold.dim_clientes') AND attnum>0 AND NOT attisdropped) IS DISTINCT FROM '[{"name": "cliente_sk", "type": "bigint", "required": true}, {"name": "customer_unique_id", "type": "text", "required": false}, {"name": "membro_tipo", "type": "text", "required": true}]'::jsonb
  OR EXISTS (SELECT 1 FROM pg_attrdef WHERE adrelid=to_regclass('gold.dim_clientes'))
  OR EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid=to_regclass('gold.dim_clientes') AND attnum>0 AND NOT attisdropped
    AND atttypid='text'::regtype AND attcollation <> '"C"'::regcollation)
  OR (SELECT count(*) FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_clientes') AND contype<>'n')<>3
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_clientes') AND contype='p'
     AND pg_get_constraintdef(oid)='PRIMARY KEY (cliente_sk)')
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_clientes') AND contype='u'
     AND pg_get_constraintdef(oid)='UNIQUE (customer_unique_id)')
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_clientes') AND contype='c'
     AND conname='dim_clientes_membros' AND convalidated)
  THEN RAISE EXCEPTION 'Dimensão preexistente incompatível: dim_clientes'; END IF;
 END IF;

 IF to_regclass('gold.dim_produtos') IS NOT NULL THEN
  IF NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.oid=to_regclass('gold.dim_produtos') AND c.relkind='r'
   AND NOT c.relrowsecurity AND NOT c.relispartition AND pg_get_userbyid(c.relowner)=current_user
   AND obj_description(c.oid,'pg_class')='inteligencia_receita:gold_dimensoes:v1:c4c2d881a3e49584825d3adfaab6a7f985d8c380d874a57b55291758f79b4aae')
  OR (SELECT jsonb_agg(jsonb_build_object('name',attname,'type',format_type(atttypid,atttypmod),'required',attnotnull) ORDER BY attnum)
   FROM pg_attribute WHERE attrelid=to_regclass('gold.dim_produtos') AND attnum>0 AND NOT attisdropped) IS DISTINCT FROM '[{"name": "produto_sk", "type": "bigint", "required": true}, {"name": "product_id", "type": "text", "required": false}, {"name": "product_category_name", "type": "text", "required": false}, {"name": "product_name_lenght", "type": "numeric", "required": false}, {"name": "product_description_lenght", "type": "numeric", "required": false}, {"name": "product_photos_qty", "type": "numeric", "required": false}, {"name": "product_weight_g", "type": "numeric", "required": false}, {"name": "product_length_cm", "type": "numeric", "required": false}, {"name": "product_height_cm", "type": "numeric", "required": false}, {"name": "product_width_cm", "type": "numeric", "required": false}, {"name": "product_category_name_english", "type": "text", "required": false}, {"name": "membro_tipo", "type": "text", "required": true}]'::jsonb
  OR EXISTS (SELECT 1 FROM pg_attrdef WHERE adrelid=to_regclass('gold.dim_produtos'))
  OR EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid=to_regclass('gold.dim_produtos') AND attnum>0 AND NOT attisdropped
    AND atttypid='text'::regtype AND attcollation <> '"C"'::regcollation)
  OR (SELECT count(*) FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_produtos') AND contype<>'n')<>3
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_produtos') AND contype='p'
     AND pg_get_constraintdef(oid)='PRIMARY KEY (produto_sk)')
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_produtos') AND contype='u'
     AND pg_get_constraintdef(oid)='UNIQUE (product_id)')
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_produtos') AND contype='c'
     AND conname='dim_produtos_membros' AND convalidated)
  THEN RAISE EXCEPTION 'Dimensão preexistente incompatível: dim_produtos'; END IF;
 END IF;

 IF to_regclass('gold.dim_vendedores') IS NOT NULL THEN
  IF NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.oid=to_regclass('gold.dim_vendedores') AND c.relkind='r'
   AND NOT c.relrowsecurity AND NOT c.relispartition AND pg_get_userbyid(c.relowner)=current_user
   AND obj_description(c.oid,'pg_class')='inteligencia_receita:gold_dimensoes:v1:51395da221c0c4a0825c9a58b30bc7e3d3772d833870c5403b7ae2815a8e6c14')
  OR (SELECT jsonb_agg(jsonb_build_object('name',attname,'type',format_type(atttypid,atttypmod),'required',attnotnull) ORDER BY attnum)
   FROM pg_attribute WHERE attrelid=to_regclass('gold.dim_vendedores') AND attnum>0 AND NOT attisdropped) IS DISTINCT FROM '[{"name": "vendedor_sk", "type": "bigint", "required": true}, {"name": "seller_id", "type": "text", "required": false}, {"name": "seller_zip_code_prefix", "type": "text", "required": false}, {"name": "seller_city", "type": "text", "required": false}, {"name": "seller_state", "type": "text", "required": false}, {"name": "membro_tipo", "type": "text", "required": true}]'::jsonb
  OR EXISTS (SELECT 1 FROM pg_attrdef WHERE adrelid=to_regclass('gold.dim_vendedores'))
  OR EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid=to_regclass('gold.dim_vendedores') AND attnum>0 AND NOT attisdropped
    AND atttypid='text'::regtype AND attcollation <> '"C"'::regcollation)
  OR (SELECT count(*) FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_vendedores') AND contype<>'n')<>3
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_vendedores') AND contype='p'
     AND pg_get_constraintdef(oid)='PRIMARY KEY (vendedor_sk)')
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_vendedores') AND contype='u'
     AND pg_get_constraintdef(oid)='UNIQUE (seller_id)')
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_vendedores') AND contype='c'
     AND conname='dim_vendedores_membros' AND convalidated)
  THEN RAISE EXCEPTION 'Dimensão preexistente incompatível: dim_vendedores'; END IF;
 END IF;

 IF to_regclass('gold.dim_calendario') IS NOT NULL THEN
  IF NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.oid=to_regclass('gold.dim_calendario') AND c.relkind='r'
   AND NOT c.relrowsecurity AND NOT c.relispartition AND pg_get_userbyid(c.relowner)=current_user
   AND obj_description(c.oid,'pg_class')='inteligencia_receita:gold_dimensoes:v1:66af41d0f4c59f3bb908673680d16d02d0405ea3d8cc5f3d2be5dbf1bf22cf06')
  OR (SELECT jsonb_agg(jsonb_build_object('name',attname,'type',format_type(atttypid,atttypmod),'required',attnotnull) ORDER BY attnum)
   FROM pg_attribute WHERE attrelid=to_regclass('gold.dim_calendario') AND attnum>0 AND NOT attisdropped) IS DISTINCT FROM '[{"name": "data_sk", "type": "bigint", "required": true}, {"name": "dia", "type": "date", "required": false}, {"name": "ano", "type": "integer", "required": false}, {"name": "mes", "type": "integer", "required": false}, {"name": "dia_mes", "type": "integer", "required": false}, {"name": "membro_tipo", "type": "text", "required": true}]'::jsonb
  OR EXISTS (SELECT 1 FROM pg_attrdef WHERE adrelid=to_regclass('gold.dim_calendario'))
  OR EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid=to_regclass('gold.dim_calendario') AND attnum>0 AND NOT attisdropped
    AND atttypid='text'::regtype AND attcollation <> '"C"'::regcollation)
  OR (SELECT count(*) FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_calendario') AND contype<>'n')<>3
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_calendario') AND contype='p'
     AND pg_get_constraintdef(oid)='PRIMARY KEY (data_sk)')
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_calendario') AND contype='u'
     AND pg_get_constraintdef(oid)='UNIQUE (dia)')
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_calendario') AND contype='c'
     AND conname='dim_calendario_membros' AND convalidated)
  THEN RAISE EXCEPTION 'Dimensão preexistente incompatível: dim_calendario'; END IF;
 END IF;

 IF to_regclass('gold.dim_localizacao') IS NOT NULL THEN
  IF NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.oid=to_regclass('gold.dim_localizacao') AND c.relkind='r'
   AND NOT c.relrowsecurity AND NOT c.relispartition AND pg_get_userbyid(c.relowner)=current_user
   AND obj_description(c.oid,'pg_class')='inteligencia_receita:gold_dimensoes:v1:e194a0e12b4ffa4f696d3508a00659893c6e94e4a24c76602c20ff4cc3e95f5a')
  OR (SELECT jsonb_agg(jsonb_build_object('name',attname,'type',format_type(atttypid,atttypmod),'required',attnotnull) ORDER BY attnum)
   FROM pg_attribute WHERE attrelid=to_regclass('gold.dim_localizacao') AND attnum>0 AND NOT attisdropped) IS DISTINCT FROM '[{"name": "localizacao_sk", "type": "bigint", "required": true}, {"name": "customer_zip_code_prefix", "type": "text", "required": false}, {"name": "customer_city", "type": "text", "required": false}, {"name": "customer_state", "type": "text", "required": false}, {"name": "membro_tipo", "type": "text", "required": true}]'::jsonb
  OR EXISTS (SELECT 1 FROM pg_attrdef WHERE adrelid=to_regclass('gold.dim_localizacao'))
  OR EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid=to_regclass('gold.dim_localizacao') AND attnum>0 AND NOT attisdropped
    AND atttypid='text'::regtype AND attcollation <> '"C"'::regcollation)
  OR (SELECT count(*) FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_localizacao') AND contype<>'n')<>3
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_localizacao') AND contype='p'
     AND pg_get_constraintdef(oid)='PRIMARY KEY (localizacao_sk)')
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_localizacao') AND contype='u'
     AND pg_get_constraintdef(oid)='UNIQUE (customer_zip_code_prefix, customer_city, customer_state)')
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_localizacao') AND contype='c'
     AND conname='dim_localizacao_membros' AND convalidated)
  THEN RAISE EXCEPTION 'Dimensão preexistente incompatível: dim_localizacao'; END IF;
 END IF;

 IF to_regclass('gold.dim_forma_pagamento') IS NOT NULL THEN
  IF NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.oid=to_regclass('gold.dim_forma_pagamento') AND c.relkind='r'
   AND NOT c.relrowsecurity AND NOT c.relispartition AND pg_get_userbyid(c.relowner)=current_user
   AND obj_description(c.oid,'pg_class')='inteligencia_receita:gold_dimensoes:v1:fd18fbd3a7995aaec9516eadb3c291f60b0173c92c2e075a0855847b66b45888')
  OR (SELECT jsonb_agg(jsonb_build_object('name',attname,'type',format_type(atttypid,atttypmod),'required',attnotnull) ORDER BY attnum)
   FROM pg_attribute WHERE attrelid=to_regclass('gold.dim_forma_pagamento') AND attnum>0 AND NOT attisdropped) IS DISTINCT FROM '[{"name": "forma_pagamento_sk", "type": "bigint", "required": true}, {"name": "payment_type", "type": "text", "required": false}, {"name": "membro_tipo", "type": "text", "required": true}]'::jsonb
  OR EXISTS (SELECT 1 FROM pg_attrdef WHERE adrelid=to_regclass('gold.dim_forma_pagamento'))
  OR EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid=to_regclass('gold.dim_forma_pagamento') AND attnum>0 AND NOT attisdropped
    AND atttypid='text'::regtype AND attcollation <> '"C"'::regcollation)
  OR (SELECT count(*) FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_forma_pagamento') AND contype<>'n')<>3
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_forma_pagamento') AND contype='p'
     AND pg_get_constraintdef(oid)='PRIMARY KEY (forma_pagamento_sk)')
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_forma_pagamento') AND contype='u'
     AND pg_get_constraintdef(oid)='UNIQUE (payment_type)')
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass('gold.dim_forma_pagamento') AND contype='c'
     AND conname='dim_forma_pagamento_membros' AND convalidated)
  THEN RAISE EXCEPTION 'Dimensão preexistente incompatível: dim_forma_pagamento'; END IF;
 END IF;
END $gold_guard$;
DO $source$ BEGIN
IF EXISTS(SELECT "customer_id" FROM silver."olist_customers_dataset" GROUP BY "customer_id" HAVING count(*)>1) THEN RAISE EXCEPTION 'Chave Silver ambígua: customers.customer_id'; END IF;
IF EXISTS(SELECT "product_id" FROM silver."olist_products_dataset" GROUP BY "product_id" HAVING count(*)>1) THEN RAISE EXCEPTION 'Chave Silver ambígua: products.product_id'; END IF;
IF EXISTS(SELECT "seller_id" FROM silver."olist_sellers_dataset" GROUP BY "seller_id" HAVING count(*)>1) THEN RAISE EXCEPTION 'Chave Silver ambígua: sellers.seller_id'; END IF;
IF EXISTS(SELECT "product_category_name" FROM silver."product_category_name_translation" GROUP BY "product_category_name" HAVING count(*)>1) THEN RAISE EXCEPTION 'Chave Silver ambígua: translation.product_category_name'; END IF;
IF EXISTS (SELECT 1 FROM silver.olist_orders_dataset o WHERE o.customer_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM silver.olist_customers_dataset c WHERE c.customer_id=o.customer_id)) THEN RAISE EXCEPTION 'Contexto de cliente não resolvido'; END IF;
END $source$;
CREATE SCHEMA IF NOT EXISTS gold;
COMMENT ON SCHEMA gold IS 'inteligencia_receita:gold_dimensoes:v1';
CREATE TABLE IF NOT EXISTS gold."dim_clientes" (
  "cliente_sk" bigint NOT NULL,
  "customer_unique_id" text COLLATE "C",
  "membro_tipo" text COLLATE "C" NOT NULL,
  CONSTRAINT "dim_clientes_pkey" PRIMARY KEY ("cliente_sk"),
  CONSTRAINT "dim_clientes_nk" UNIQUE ("customer_unique_id"),
  CONSTRAINT "dim_clientes_membros" CHECK ((("cliente_sk"=-1 AND membro_tipo='nao_informado' AND "customer_unique_id" IS NULL) OR ("cliente_sk"=-2 AND membro_tipo='referencia_nao_encontrada' AND "customer_unique_id" IS NULL) OR ("cliente_sk">0 AND membro_tipo='regular' AND "customer_unique_id" IS NOT NULL)))
);
COMMENT ON TABLE gold."dim_clientes" IS 'inteligencia_receita:gold_dimensoes:v1:cc484a45e7406a1c84f259137897c554e2c73012a8fc756b63cbb8b181ddb346';
CREATE TABLE IF NOT EXISTS gold."dim_produtos" (
  "produto_sk" bigint NOT NULL,
  "product_id" text COLLATE "C",
  "product_category_name" text COLLATE "C",
  "product_name_lenght" numeric,
  "product_description_lenght" numeric,
  "product_photos_qty" numeric,
  "product_weight_g" numeric,
  "product_length_cm" numeric,
  "product_height_cm" numeric,
  "product_width_cm" numeric,
  "product_category_name_english" text COLLATE "C",
  "membro_tipo" text COLLATE "C" NOT NULL,
  CONSTRAINT "dim_produtos_pkey" PRIMARY KEY ("produto_sk"),
  CONSTRAINT "dim_produtos_nk" UNIQUE ("product_id"),
  CONSTRAINT "dim_produtos_membros" CHECK ((("produto_sk"=-1 AND membro_tipo='nao_informado' AND "product_id" IS NULL AND "product_category_name" IS NULL AND "product_name_lenght" IS NULL AND "product_description_lenght" IS NULL AND "product_photos_qty" IS NULL AND "product_weight_g" IS NULL AND "product_length_cm" IS NULL AND "product_height_cm" IS NULL AND "product_width_cm" IS NULL AND "product_category_name_english" IS NULL) OR ("produto_sk"=-2 AND membro_tipo='referencia_nao_encontrada' AND "product_id" IS NULL AND "product_category_name" IS NULL AND "product_name_lenght" IS NULL AND "product_description_lenght" IS NULL AND "product_photos_qty" IS NULL AND "product_weight_g" IS NULL AND "product_length_cm" IS NULL AND "product_height_cm" IS NULL AND "product_width_cm" IS NULL AND "product_category_name_english" IS NULL) OR ("produto_sk">0 AND membro_tipo='regular' AND "product_id" IS NOT NULL)))
);
COMMENT ON TABLE gold."dim_produtos" IS 'inteligencia_receita:gold_dimensoes:v1:c4c2d881a3e49584825d3adfaab6a7f985d8c380d874a57b55291758f79b4aae';
CREATE TABLE IF NOT EXISTS gold."dim_vendedores" (
  "vendedor_sk" bigint NOT NULL,
  "seller_id" text COLLATE "C",
  "seller_zip_code_prefix" text COLLATE "C",
  "seller_city" text COLLATE "C",
  "seller_state" text COLLATE "C",
  "membro_tipo" text COLLATE "C" NOT NULL,
  CONSTRAINT "dim_vendedores_pkey" PRIMARY KEY ("vendedor_sk"),
  CONSTRAINT "dim_vendedores_nk" UNIQUE ("seller_id"),
  CONSTRAINT "dim_vendedores_membros" CHECK ((("vendedor_sk"=-1 AND membro_tipo='nao_informado' AND "seller_id" IS NULL AND "seller_zip_code_prefix" IS NULL AND "seller_city" IS NULL AND "seller_state" IS NULL) OR ("vendedor_sk"=-2 AND membro_tipo='referencia_nao_encontrada' AND "seller_id" IS NULL AND "seller_zip_code_prefix" IS NULL AND "seller_city" IS NULL AND "seller_state" IS NULL) OR ("vendedor_sk">0 AND membro_tipo='regular' AND "seller_id" IS NOT NULL)))
);
COMMENT ON TABLE gold."dim_vendedores" IS 'inteligencia_receita:gold_dimensoes:v1:51395da221c0c4a0825c9a58b30bc7e3d3772d833870c5403b7ae2815a8e6c14';
CREATE TABLE IF NOT EXISTS gold."dim_calendario" (
  "data_sk" bigint NOT NULL,
  "dia" date,
  "ano" integer,
  "mes" integer,
  "dia_mes" integer,
  "membro_tipo" text COLLATE "C" NOT NULL,
  CONSTRAINT "dim_calendario_pkey" PRIMARY KEY ("data_sk"),
  CONSTRAINT "dim_calendario_nk" UNIQUE ("dia"),
  CONSTRAINT "dim_calendario_membros" CHECK ((("data_sk"=-1 AND membro_tipo='nao_informado' AND "dia" IS NULL AND "ano" IS NULL AND "mes" IS NULL AND "dia_mes" IS NULL) OR ("data_sk"=-2 AND membro_tipo='referencia_nao_encontrada' AND "dia" IS NULL AND "ano" IS NULL AND "mes" IS NULL AND "dia_mes" IS NULL) OR ("data_sk">0 AND membro_tipo='regular' AND "dia" IS NOT NULL)))
);
COMMENT ON TABLE gold."dim_calendario" IS 'inteligencia_receita:gold_dimensoes:v1:66af41d0f4c59f3bb908673680d16d02d0405ea3d8cc5f3d2be5dbf1bf22cf06';
CREATE TABLE IF NOT EXISTS gold."dim_localizacao" (
  "localizacao_sk" bigint NOT NULL,
  "customer_zip_code_prefix" text COLLATE "C",
  "customer_city" text COLLATE "C",
  "customer_state" text COLLATE "C",
  "membro_tipo" text COLLATE "C" NOT NULL,
  CONSTRAINT "dim_localizacao_pkey" PRIMARY KEY ("localizacao_sk"),
  CONSTRAINT "dim_localizacao_nk" UNIQUE ("customer_zip_code_prefix","customer_city","customer_state"),
  CONSTRAINT "dim_localizacao_membros" CHECK ((("localizacao_sk"=-1 AND membro_tipo='nao_informado' AND "customer_zip_code_prefix" IS NULL AND "customer_city" IS NULL AND "customer_state" IS NULL) OR ("localizacao_sk"=-2 AND membro_tipo='referencia_nao_encontrada' AND "customer_zip_code_prefix" IS NULL AND "customer_city" IS NULL AND "customer_state" IS NULL) OR ("localizacao_sk">0 AND membro_tipo='regular' AND "customer_zip_code_prefix" IS NOT NULL AND "customer_city" IS NOT NULL AND "customer_state" IS NOT NULL)))
);
COMMENT ON TABLE gold."dim_localizacao" IS 'inteligencia_receita:gold_dimensoes:v1:e194a0e12b4ffa4f696d3508a00659893c6e94e4a24c76602c20ff4cc3e95f5a';
CREATE TABLE IF NOT EXISTS gold."dim_forma_pagamento" (
  "forma_pagamento_sk" bigint NOT NULL,
  "payment_type" text COLLATE "C",
  "membro_tipo" text COLLATE "C" NOT NULL,
  CONSTRAINT "dim_forma_pagamento_pkey" PRIMARY KEY ("forma_pagamento_sk"),
  CONSTRAINT "dim_forma_pagamento_nk" UNIQUE ("payment_type"),
  CONSTRAINT "dim_forma_pagamento_membros" CHECK ((("forma_pagamento_sk"=-1 AND membro_tipo='nao_informado' AND "payment_type" IS NULL) OR ("forma_pagamento_sk"=-2 AND membro_tipo='referencia_nao_encontrada' AND "payment_type" IS NULL) OR ("forma_pagamento_sk">0 AND membro_tipo='regular' AND "payment_type" IS NOT NULL)))
);
COMMENT ON TABLE gold."dim_forma_pagamento" IS 'inteligencia_receita:gold_dimensoes:v1:fd18fbd3a7995aaec9516eadb3c291f60b0173c92c2e075a0855847b66b45888';
