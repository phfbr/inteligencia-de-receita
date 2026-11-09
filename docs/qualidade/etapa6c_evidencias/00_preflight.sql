\set ON_ERROR_STOP on
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL search_path=pg_catalog;
SET LOCAL datestyle='ISO, YMD';
SET LOCAL standard_conforming_strings=on;
SET LOCAL statement_timeout='15min';
SET LOCAL lock_timeout='5s';
SELECT set_config('olist.expected_database','inteligencia_receita_db',true) IS NOT NULL;
SELECT json_build_object('database',current_database(),'usuario',current_user,'sessao',session_user,'proprietario',pg_get_userbyid(datdba),'marker',shobj_description(oid,'pg_database'),'read_only',current_setting('transaction_read_only'),'isolation',current_setting('transaction_isolation'),'version',current_setting('server_version'),'instante',clock_timestamp()) FROM pg_database WHERE datname=current_database();
ROLLBACK;
