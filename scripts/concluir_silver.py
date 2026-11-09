"""Conclui a Silver reutilizando carregador e testes, com evidências persistentes."""
import argparse
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import silver as s

DATABASE = 'inteligencia_receita_db'


def run_sql(work, name, text):
    path = work / (name + '.sql')
    path.write_text(text, encoding='utf-8')
    return s.run_psql(path)


def initial_guard():
    """Apenas admite comentário vazio para inspecionar um banco novo, sem adotar objetos."""
    original = "AND shobj_description(d.oid,'pg_database')=" + s.literal(s.PROJECT)
    replacement = ("AND (shobj_description(d.oid,'pg_database') IS NULL OR "
                   "shobj_description(d.oid,'pg_database')=" + s.literal(s.PROJECT) + ')')
    guard = s.guard_sql()
    if guard.count(original) != 1:
        raise s.SilverError('A proteção do carregador mudou; revisar inicialização antes de prosseguir.')
    return guard.replace(original, replacement)


def inspect_and_identify(work):
    # A autorização refere-se exclusivamente a este banco nominal.
    if os.environ.get('PGDATABASE') != DATABASE or os.environ.get('OLIST_PROJECT_DATABASE') != DATABASE:
        raise s.SilverError('A conclusão desta etapa exige inteligencia_receita_db em ambos os parâmetros.')
    inspection = """SELECT json_build_object(
 'database',current_database(),'user',current_user,'owner',pg_get_userbyid(d.datdba),
 'server_version',current_setting('server_version'),'server_encoding',current_setting('server_encoding'),
 'marker_missing',shobj_description(d.oid,'pg_database') IS NULL,
 'marker_matches',COALESCE(shobj_description(d.oid,'pg_database')='inteligencia_receita:exclusive:v1',false),
 'user_relations',COALESCE((SELECT json_agg(json_build_object('schema',n.nspname,'name',c.relname,'kind',c.relkind)
 ORDER BY n.nspname,c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'),'[]'::json))
FROM pg_database d WHERE d.datname=current_database();
"""
    rows = run_sql(work, 'isolation_before', s.transaction_prefix(True) + initial_guard() + inspection + 'ROLLBACK;\n')
    if len(rows) != 1 or rows[0]['database'] != DATABASE or rows[0]['owner'] != rows[0]['user']:
        raise s.SilverError('A identidade e a propriedade do banco não foram confirmadas.')
    before = rows[0]
    if before['marker_missing']:
        if before['user_relations']:
            raise s.SilverError('Banco sem marcador contém objetos preexistentes; nenhuma identificação automática realizada.')
        # O usuário declarou este banco exclusivo. Só identificamos se continuar vazio.
        empty_guard = """DO $empty$ BEGIN
IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema') THEN
 RAISE EXCEPTION 'Objetos surgiram após inspeção; inicialização recusada';
END IF;
IF EXISTS (SELECT 1 FROM pg_database d WHERE d.datname=current_database()
 AND shobj_description(d.oid,'pg_database') IS NOT NULL) THEN
 RAISE EXCEPTION 'Comentário mudou após inspeção; inicialização recusada';
END IF;
END $empty$;
"""
        run_sql(work, 'identify_empty_project_database', s.transaction_prefix() +
                'SELECT pg_advisory_xact_lock(871204031);\n' + initial_guard() + empty_guard +
                f'COMMENT ON DATABASE {s.ident(DATABASE)} IS {s.literal(s.PROJECT)};\n' +
                s.guard_sql() + 'COMMIT;\n')
    elif not before['marker_matches']:
        raise s.SilverError('Comentário existente não identifica o projeto; não será sobrescrito.')
    after = s.preflight(work)
    return dict(before=before, database_comment_initialized=before['marker_missing'], confirmed=after)


def detailed_sql():
    sql = []
    for entity in s.TABLES:
        nulls = ','.join(s.literal(name) + f',count(*) FILTER (WHERE {s.ident(name)} IS NULL)'
                         for name, _ in s.columns(entity))
        totals = ','.join(s.literal(name) + f',sum({s.ident(name)})::text'
                          for name, kind in s.columns(entity) if kind == 'numeric')
        sql.append(f"SELECT json_build_object('entity',{s.literal(entity)},'rows',count(*),"
                   f"'nulls',json_build_object({nulls}),'numeric_sums',json_build_object({totals})) FROM {s.table(entity)};\n")
        for fields in s.KEYS[entity]:
            group = ','.join(s.ident(name) for name in fields)
            sql.append(f"SELECT json_build_object('entity',{s.literal(entity)},'key',{s.literal(' + '.join(fields))},"
                       f"'distinct',count(*),'duplicate_excess',COALESCE(sum(n-1),0)::bigint) FROM "
                       f"(SELECT {group},count(*) n FROM {s.table(entity)} GROUP BY {group}) k;\n")
    sql.append("""SELECT json_build_object('columns',json_agg(json_build_object(
 'table',c.relname,'column',a.attname,'type',format_type(a.atttypid,a.atttypmod),'not_null',a.attnotnull)
 ORDER BY c.relname,a.attnum)) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 JOIN pg_attribute a ON a.attrelid=c.oid WHERE n.nspname='silver' AND c.relkind='r'
 AND a.attnum>0 AND NOT a.attisdropped;
""")
    return ''.join(sql)


def complete(output):
    output.mkdir(parents=True, exist_ok=False)
    summary = dict(started_utc=datetime.now(timezone.utc).isoformat(), database=DATABASE,
                   status='started', errors=[], environment=s.environment_status())
    try:
        if summary['environment']['blockers']:
            summary['status'] = 'blocked'
            return summary
        with tempfile.TemporaryDirectory(prefix='olist_conclusao_') as folder:
            work = Path(folder)
            summary['isolation'] = inspect_and_identify(work)
            print('Destino e isolamento confirmados; iniciando testes reais da Silver.', flush=True)
            previous = {name: os.environ.get(name) for name in ('OLIST_RUN_DB_TESTS', 'OLIST_DB_EVIDENCE_DIR')}
            try:
                os.environ['OLIST_RUN_DB_TESTS'] = '1'
                os.environ['OLIST_DB_EVIDENCE_DIR'] = str(output / 'integracao')
                suite = unittest.defaultTestLoader.discover(str(s.ROOT / 'tests'), pattern='test_*.py')
                with (output / 'testes.log').open('w', encoding='utf-8') as stream:
                    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
                summary['tests'] = dict(total=result.testsRun, failures=len(result.failures),
                                        errors=len(result.errors), skipped=len(result.skipped))
                if not result.wasSuccessful() or result.skipped:
                    raise s.SilverError('Testes não concluídos integralmente; consultar evidências, sem declarar carga validada.')
            finally:
                for name, value in previous.items():
                    if value is None:
                        os.environ.pop(name, None)
                    else:
                        os.environ[name] = value
            reports = {name: json.loads((output / 'integracao' / name / 'resultado.json').read_text(encoding='utf-8'))
                       for name in ('first', 'second', 'rollback', 'verify')}
            summary['runs'] = {name: report['status'] for name, report in reports.items()}
            summary['idempotence_confirmed'] = reports['first']['database_results'] == reports['second']['database_results']
            summary['rollback_confirmed'] = (reports['rollback']['status'] == 'failed' and
                any('SQLSTATE 22012' in e for e in reports['rollback']['errors']) and
                reports['verify']['status'] == 'verified_readonly' and
                reports['second']['database_results'] == reports['verify']['database_results'])
            summary['database_results'] = reports['verify']['database_results']
            summary['source_hashes'] = {entity: stats['sha256'] for entity, stats in reports['verify']['sources'].items()}
            summary['detailed_database_results'] = run_sql(work, 'final_details', s.transaction_prefix(True) +
                s.guard_sql() + detailed_sql() + 'ROLLBACK;\n')
            summary['status'] = 'completed_verified'
    except Exception as exc:
        summary['status'] = 'failed'
        summary['errors'].append(str(exc) if isinstance(exc, s.SilverError) else type(exc).__name__)
    finally:
        summary['finished_utc'] = datetime.now(timezone.utc).isoformat()
        (output / 'conclusao.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=s.ROOT / 'docs/qualidade/etapa4_silver' /
                        ('conclusao_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')))
    args = parser.parse_args()
    result = complete(args.output.resolve())
    print(json.dumps(dict(status=result['status'], output=str(args.output), errors=result['errors']), ensure_ascii=True))
    raise SystemExit(0 if result['status'] == 'completed_verified' else 2 if result['status'] == 'blocked' else 1)


if __name__ == '__main__':
    main()
