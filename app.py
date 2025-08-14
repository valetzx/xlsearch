from flask import Flask, render_template, request, jsonify
from database import init_db, get_conn
from file_indexer import index_files
import threading
import time
import logging
import os
from config import XLSX_DIR, DB_PATH, AUTH_PASSWORD

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


# 后台索引线程
def background_indexer():
    while True:
        index_files()
        time.sleep(300)  # 每5分钟检查一次


def initialize():
    """Initialize database and start background indexer."""
    init_db()
    threading.Thread(target=background_indexer, daemon=True).start()


# 初始化应用程序
initialize()

@app.route('/')
def home():
    return render_template('index.html', xlsx_dir=XLSX_DIR)

@app.route('/search')
def search():
    if request.args.get('password') != AUTH_PASSWORD:
        return jsonify(error='unauthorized'), 401

    query = request.args.get('q', '')
    extra = request.args.get('extra', '')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    exclude = request.args.get('exclude', '')

    excluded_files = [e.strip() for e in exclude.split(',') if e.strip()]
    extra_terms = [e.strip() for e in extra.split(',') if e.strip()]

    conn = get_conn()
    c = conn.cursor()

    terms = [t for t in [query] + extra_terms if t]

    try:
        if not terms:
            base_query = (
                "SELECT f.path, fts.sheet_name, fts.row_index, "
                "substr(fts.content, 1, 100) AS snippet "
                "FROM fts_index fts "
                "JOIN files f ON f.id = fts.file_id"
            )
            params = []
            if excluded_files:
                placeholders = " AND ".join(["f.path NOT LIKE ?"] * len(excluded_files))
                base_query += " WHERE " + placeholders
                params.extend([f"%{name}%" for name in excluded_files])
            base_query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            c.execute(base_query, params)
            results = [
                {
                    "file": row[0],
                    "sheet": row[1],
                    "row": row[2] + 1,
                    "snippet": row[3],
                }
                for row in c.fetchall()
            ]
            count_query = (
                "SELECT COUNT(*) FROM fts_index fts JOIN files f ON f.id = fts.file_id"
            )
            count_params = []
            if excluded_files:
                placeholders = " AND ".join(["f.path NOT LIKE ?"] * len(excluded_files))
                count_query += " WHERE " + placeholders
                count_params.extend([f"%{name}%" for name in excluded_files])
            c.execute(count_query, count_params)
            full_count = c.fetchone()[0]
        else:
            first = terms[0]
            like_conditions = " AND ".join(["fts.content LIKE ?"] * len(terms))
            base_query = (
                "SELECT f.path, fts.sheet_name, fts.row_index, "
                "substr(fts.content, CASE WHEN instr(fts.content, ?) > 25 "
                "THEN instr(fts.content, ?) - 25 ELSE 1 END, 100) AS snippet "
                "FROM fts_index fts JOIN files f ON f.id = fts.file_id "
                "WHERE " + like_conditions
            )
            params = [first, first] + [f"%{t}%" for t in terms]
            if excluded_files:
                placeholders = " AND ".join(["f.path NOT LIKE ?"] * len(excluded_files))
                base_query += " AND " + placeholders
                params.extend([f"%{name}%" for name in excluded_files])
            base_query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            c.execute(base_query, params)

            results = []
            for row in c.fetchall():
                snippet = row[3] or ""
                for t in terms:
                    snippet = snippet.replace(t, f"<b>{t}</b>")
                results.append(
                    {
                        "file": row[0],
                        "sheet": row[1],
                        "row": row[2] + 1,
                        "snippet": snippet,
                    }
                )
            count_query = (
                "SELECT COUNT(*) FROM fts_index fts JOIN files f ON f.id = fts.file_id "
                "WHERE " + like_conditions
            )
            count_params = [f"%{t}%" for t in terms]
            if excluded_files:
                placeholders = " AND ".join(["f.path NOT LIKE ?"] * len(excluded_files))
                count_query += " AND " + placeholders
                count_params.extend([f"%{name}%" for name in excluded_files])
            c.execute(count_query, count_params)
            full_count = c.fetchone()[0]

        return jsonify(results=results, count=full_count)
    except Exception:
        app.logger.exception("搜索失败")
        return jsonify(results=[], count=0, error="internal error"), 500
    finally:
        conn.close()


@app.route('/reset_db', methods=['POST'])
def reset_db():
    data = request.get_json() or {}
    if data.get('password') != AUTH_PASSWORD:
        return jsonify(error='unauthorized'), 401
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
    index_files()
    return jsonify(status='ok')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
