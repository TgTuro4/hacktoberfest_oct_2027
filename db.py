"""Thin wrapper around the Snowflake connector for calling LIFEDATA.MAIN procedures."""
import os
from contextlib import contextmanager

import snowflake.connector
from snowflake.connector import DictCursor


@contextmanager
def get_conn():
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],  # swap for key-pair auth in production
        role=os.environ.get("SNOWFLAKE_ROLE", "LIFEDATA_API_ROLE"),
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database="LIFEDATA",
        schema="MAIN",
    )
    try:
        yield conn
    finally:
        conn.close()


def _call(proc: str, args: tuple, dict_rows: bool):
    # `proc` is always a hard-coded constant from this module, never user input.
    placeholders = ", ".join(["%s"] * len(args))
    sql = f"CALL LIFEDATA.MAIN.{proc}({placeholders})"
    with get_conn() as conn:
        cur = conn.cursor(DictCursor) if dict_rows else conn.cursor()
        try:
            cur.execute(sql, args)
            return cur.fetchall() if dict_rows else cur.fetchone()[0]
        finally:
            cur.close()


# --- procedure wrappers ------------------------------------------------------

def create_user(name: str, email: str, username: str, password_hash: str) -> str:
    return _call("CREATE_USER", (name, email, username, password_hash), dict_rows=False)


def create_profile(user_id: int, name: str, major: str | None, bio: str | None) -> str:
    return _call("CREATE_PROFILE", (user_id, name, major, bio), dict_rows=False)


def get_user(email: str) -> list[dict]:
    return _call("GET_USER", (email,), dict_rows=True)


def get_user_by_id(user_id: int) -> list[dict]:
    return _call("GET_USER_BY_ID", (user_id,), dict_rows=True)


def get_profile(user_id: int) -> list[dict]:
    return _call("GET_PROFILE", (user_id,), dict_rows=True)
