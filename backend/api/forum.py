"""Foro estilo Reddit — endpoints Online (subreddits, posts, votos, comentarios)."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/forum", tags=["forum"])

_DB_PATH = Path(__file__).resolve().parent.parent / "forum.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def _init() -> None:
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS subreddits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT '',
                created_at REAL
            );
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subreddit_id INTEGER REFERENCES subreddits(id) ON DELETE CASCADE,
                author TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT DEFAULT '',
                created_at REAL
            );
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER REFERENCES posts(id) ON DELETE CASCADE,
                parent_id INTEGER REFERENCES comments(id) ON DELETE CASCADE,
                author TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at REAL
            );
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_type TEXT NOT NULL,          -- 'post' | 'comment'
                target_id INTEGER NOT NULL,
                voter TEXT NOT NULL,                 -- id estable del usuario (localStorage)
                value INTEGER NOT NULL,              -- 1 = up, -1 = down
                UNIQUE(target_type, target_id, voter)
            );
            """
        )
        # subreddit por defecto
        c.execute(
            "INSERT OR IGNORE INTO subreddits (name, description, created_at) VALUES (?,?,?)",
            ("general", "Comunidad general", time.time()),
        )


_init()


# ---------- modelos ----------
class SubredditIn(BaseModel):
    name: str = Field(min_length=2, max_length=30)
    description: str = ""


class PostIn(BaseModel):
    subreddit: str = "general"
    author: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=3, max_length=200)
    body: str = ""


class CommentIn(BaseModel):
    author: str = Field(min_length=1, max_length=40)
    body: str = Field(min_length=1, max_length=2000)
    parent_id: int | None = None


class VoteIn(BaseModel):
    voter: str = Field(min_length=1, max_length=64)
    value: int  # 1, -1, 0 (0 = quitar voto)


# ---------- helpers ----------
def _score_expr(target_type: str, target_col: str) -> str:
    return (
        f"COALESCE((SELECT SUM(value) FROM votes WHERE target_type='{target_type}' "
        f"AND target_id={target_col}),0)"
    )


def _get_subreddit_id(c: sqlite3.Connection, name: str) -> int:
    row = c.execute("SELECT id FROM subreddits WHERE name=?", (name,)).fetchone()
    if not row:
        raise HTTPException(404, f"El subforo '{name}' no existe")
    return row["id"]


# ---------- subreddits ----------
@router.get("/subreddits")
def list_subreddits() -> dict:
    with _conn() as c:
        rows = c.execute(
            f"""SELECT s.id, s.name, s.description,
                       (SELECT COUNT(*) FROM posts p WHERE p.subreddit_id=s.id) AS posts
                FROM subreddits s ORDER BY s.name"""
        ).fetchall()
        return {"subreddits": [dict(r) for r in rows]}


@router.post("/subreddits")
def create_subreddit(data: SubredditIn) -> dict:
    name = data.name.strip().lower().replace(" ", "-")
    with _conn() as c:
        try:
            c.execute(
                "INSERT INTO subreddits (name, description, created_at) VALUES (?,?,?)",
                (name, data.description, time.time()),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Ese subforo ya existe")
        return {"ok": True, "name": name}


# ---------- posts ----------
@router.get("/posts")
def list_posts(
    subreddit: str | None = None,
    sort: str = Query("hot", pattern="^(hot|new|top)$"),
    limit: int = 50,
) -> dict:
    with _conn() as c:
        where = ""
        args: list = []
        if subreddit:
            sid = _get_subreddit_id(c, subreddit)
            where = "WHERE p.subreddit_id=?"
            args.append(sid)
        score = _score_expr("post", "p.id")
        comments = "(SELECT COUNT(*) FROM comments cm WHERE cm.post_id=p.id)"
        if sort == "new":
            order = "p.created_at DESC"
        elif sort == "top":
            order = f"{score} DESC, p.created_at DESC"
        else:  # hot: score / (edad en horas ^ 1.5)
            order = f"({score} + 1.0) / POWER(((({{ts}}) - p.created_at)/3600.0) + 2, 1.5) DESC".format(ts=time.time())
        rows = c.execute(
            f"""SELECT p.id, p.title, p.body, p.author, p.created_at,
                       s.name AS subreddit, {score} AS score, {comments} AS comments
                FROM posts p JOIN subreddits s ON s.id=p.subreddit_id
                {where} ORDER BY {order} LIMIT ?""",
            (*args, limit),
        ).fetchall()
        return {"posts": [dict(r) for r in rows]}


@router.post("/posts")
def create_post(data: PostIn) -> dict:
    with _conn() as c:
        sid = _get_subreddit_id(c, data.subreddit)
        cur = c.execute(
            "INSERT INTO posts (subreddit_id, author, title, body, created_at) VALUES (?,?,?,?,?)",
            (sid, data.author.strip(), data.title.strip(), data.body.strip(), time.time()),
        )
        return {"ok": True, "id": cur.lastrowid}


@router.get("/posts/{post_id}")
def get_post(post_id: int) -> dict:
    with _conn() as c:
        score = _score_expr("post", "p.id")
        row = c.execute(
            f"""SELECT p.id, p.title, p.body, p.author, p.created_at,
                       s.name AS subreddit, {score} AS score
                FROM posts p JOIN subreddits s ON s.id=p.subreddit_id WHERE p.id=?""",
            (post_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Post no encontrado")
        return dict(row)


@router.delete("/posts/{post_id}")
def delete_post(post_id: int, author: str = Query(default="")) -> dict:
    with _conn() as c:
        row = c.execute("SELECT author FROM posts WHERE id=?", (post_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Post no encontrado")
        if author and row["author"] != author:
            raise HTTPException(403, "Solo el autor puede borrar")
        c.execute("DELETE FROM posts WHERE id=?", (post_id,))
        return {"ok": True}


# ---------- comentarios ----------
@router.get("/posts/{post_id}/comments")
def list_comments(post_id: int) -> dict:
    with _conn() as c:
        score = _score_expr("comment", "cm.id")
        rows = c.execute(
            f"""SELECT cm.id, cm.post_id, cm.parent_id, cm.author, cm.body, cm.created_at, {score} AS score
                FROM comments cm WHERE cm.post_id=? ORDER BY cm.created_at ASC""",
            (post_id,),
        ).fetchall()
        return {"comments": [dict(r) for r in rows]}


@router.post("/posts/{post_id}/comments")
def add_comment(post_id: int, data: CommentIn) -> dict:
    with _conn() as c:
        if not c.execute("SELECT 1 FROM posts WHERE id=?", (post_id,)).fetchone():
            raise HTTPException(404, "Post no encontrado")
        if data.parent_id is not None:
            ok = c.execute(
                "SELECT 1 FROM comments WHERE id=? AND post_id=?", (data.parent_id, post_id)
            ).fetchone()
            if not ok:
                raise HTTPException(400, "Comentario padre inválido")
        cur = c.execute(
            "INSERT INTO comments (post_id, parent_id, author, body, created_at) VALUES (?,?,?,?,?)",
            (post_id, data.parent_id, data.author.strip(), data.body.strip(), time.time()),
        )
        return {"ok": True, "id": cur.lastrowid}


# ---------- votos ----------
@router.post("/vote/{target_type}/{target_id}")
def vote_target(target_type: str, target_id: int, data: VoteIn) -> dict:
    if target_type not in ("post", "comment") or data.value not in (1, -1, 0):
        raise HTTPException(422, "Parámetros inválidos")
    table = "posts" if target_type == "post" else "comments"
    with _conn() as c:
        if not c.execute(f"SELECT 1 FROM {table} WHERE id=?", (target_id,)).fetchone():
            raise HTTPException(404, "No encontrado")
        if data.value == 0:
            c.execute(
                "DELETE FROM votes WHERE target_type=? AND target_id=? AND voter=?",
                (target_type, target_id, data.voter),
            )
        else:
            c.execute(
                "INSERT INTO votes (target_type, target_id, voter, value) VALUES (?,?,?,?) "
                "ON CONFLICT(target_type, target_id, voter) DO UPDATE SET value=excluded.value",
                (target_type, target_id, data.voter, data.value),
            )
        score = c.execute(
            "SELECT COALESCE(SUM(value),0) AS s FROM votes WHERE target_type=? AND target_id=?",
            (target_type, target_id),
        ).fetchone()["s"]
        return {"ok": True, "score": score}
