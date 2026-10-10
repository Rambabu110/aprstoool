"""
api/services/db_explorer_service.py — Safe read-only Database Explorer service.
Enforces table name allowlist against sqlite_master.
Never allows arbitrary SQL, UPDATE, DELETE, INSERT, or ALTER.
"""
import os
import time
from typing import Optional, List, Dict, Any, Set
from core.database import get_connection, get_db_path
from api.schemas.db_explorer import (
    TableInfo,
    ColumnInfo,
    ForeignKeyInfo,
    TableSchemaResponse,
    DatabaseOverviewResponse,
    TableRowsResponse
)


class DbExplorerService:
    @staticmethod
    def _get_allowlisted_tables() -> Set[str]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = {row[0] for row in cur.fetchall()}
        conn.close()
        return tables

    @classmethod
    def get_overview(cls) -> DatabaseOverviewResponse:
        db_path = get_db_path()
        file_size = 0
        last_modified = "N/A"
        if os.path.exists(db_path):
            stat = os.stat(db_path)
            file_size = stat.st_size
            last_modified = time.ctime(stat.st_mtime)

        conn = get_connection()
        cur = conn.cursor()

        # Integrity
        cur.execute("PRAGMA integrity_check")
        integrity_res = cur.fetchone()
        integrity_status = integrity_res[0] if integrity_res else "unknown"

        # FK check
        cur.execute("PRAGMA foreign_key_check")
        fk_violations = len(cur.fetchall())

        # Table list & counts
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        table_names = [r[0] for r in cur.fetchall()]

        tables_info: List[TableInfo] = []
        for name in table_names:
            # Query count safely using quotes around allowlisted identifier
            cur.execute(f'SELECT COUNT(*) FROM "{name}"')
            cnt = cur.fetchone()[0]
            tables_info.append(TableInfo(name=name, row_count=cnt))

        conn.close()

        return DatabaseOverviewResponse(
            database_file=os.path.basename(db_path),
            file_size_bytes=file_size,
            last_modified=last_modified,
            integrity_status=integrity_status,
            foreign_key_violations_count=fk_violations,
            total_tables=len(tables_info),
            tables=tables_info
        )

    @classmethod
    def get_table_schema(cls, table_name: str) -> Optional[TableSchemaResponse]:
        allowed = cls._get_allowlisted_tables()
        if table_name not in allowed:
            return None

        conn = get_connection()
        cur = conn.cursor()

        # Row count
        cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        row_count = cur.fetchone()[0]

        # Columns
        cur.execute(f'PRAGMA table_info("{table_name}")')
        col_rows = cur.fetchall()
        columns = [
            ColumnInfo(
                cid=r[0],
                name=r[1],
                data_type=r[2] or "TEXT",
                notnull=bool(r[3]),
                default_value=str(r[4]) if r[4] is not None else None,
                pk=bool(r[5])
            )
            for r in col_rows
        ]

        # Foreign keys
        cur.execute(f'PRAGMA foreign_key_list("{table_name}")')
        fk_rows = cur.fetchall()
        foreign_keys = [
            ForeignKeyInfo(
                id=r[0],
                seq=r[1],
                table=r[2],
                from_col=r[3],
                to_col=r[4]
            )
            for r in fk_rows
        ]

        conn.close()

        return TableSchemaResponse(
            table_name=table_name,
            row_count=row_count,
            columns=columns,
            foreign_keys=foreign_keys
        )

    @classmethod
    def get_table_rows(
        cls,
        table_name: str,
        page: int = 1,
        page_size: int = 25,
        search: Optional[str] = None
    ) -> Optional[TableRowsResponse]:
        allowed = cls._get_allowlisted_tables()
        if table_name not in allowed:
            return None

        conn = get_connection()
        cur = conn.cursor()

        # Get columns
        cur.execute(f'PRAGMA table_info("{table_name}")')
        col_rows = cur.fetchall()
        col_names = [r[1] for r in col_rows]

        offset = (page - 1) * page_size

        # If search query provided, search text columns safely
        where_clauses = []
        params = []
        if search and search.strip():
            kw = f"%{search.strip()}%"
            for col in col_names:
                where_clauses.append(f'CAST("{col}" AS TEXT) LIKE ?')
                params.append(kw)

        where_sql = f"WHERE {' OR '.join(where_clauses)}" if where_clauses else ""

        # Total matching
        count_sql = f'SELECT COUNT(*) FROM "{table_name}" {where_sql}'
        cur.execute(count_sql, params)
        total_rows = cur.fetchone()[0]

        # Paginated rows
        query_sql = f'SELECT * FROM "{table_name}" {where_sql} LIMIT ? OFFSET ?'
        cur.execute(query_sql, params + [page_size, offset])
        data_rows = cur.fetchall()
        conn.close()

        # Serialize rows as list of dicts with stringified objects
        result_rows: List[Dict[str, Any]] = []
        for r in data_rows:
            row_dict = {}
            for col, val in zip(col_names, r):
                if isinstance(val, (bytes, bytearray)):
                    row_dict[col] = "<binary data>"
                else:
                    row_dict[col] = val
            result_rows.append(row_dict)

        return TableRowsResponse(
            table_name=table_name,
            total_rows=total_rows,
            page=page,
            page_size=page_size,
            columns=col_names,
            rows=result_rows
        )
