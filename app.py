from flask import Flask, render_template, request, jsonify
from database import init_db, get_conn
from file_indexer import index_files
import threading
import time
import logging
from config import XLSX_DIR

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# 后台索引线程
def background_indexer():
    while True:
        index_files()
        time.sleep(300)  # 每5分钟检查一次

@app.before_first_request
def initialize():
    init_db()
    # 启动后台索引线程
    threading.Thread(target=background_indexer, daemon=True).start()

@app.route('/')
def home():
    return render_template('index.html', xlsx_dir=XLSX_DIR)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))

    conn = get_conn()
    c = conn.cursor()

    try:
        if not query:
            c.execute(
                """
                SELECT f.path, fts.sheet_name, fts.row_index,
                       substr(fts.content, 1, 100) AS snippet
                FROM fts_index fts
                JOIN files f ON f.id = fts.file_id
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            results = [
                {
                    "file": row[0],
                    "sheet": row[1],
                    "row": row[2] + 1,
                    "snippet": row[3],
                }
                for row in c.fetchall()
            ]
            c.execute("SELECT COUNT(*) FROM fts_index")
            full_count = c.fetchone()[0]
        else:
            # 使用FTS5进行高效搜索
            c.execute(
                """
                SELECT
                    f.path,
                    fts.sheet_name,
                    fts.row_index,
                    snippet(fts_index, 3, '<b>', '</b>', '...', 64) as snippet,
                    COUNT(*) OVER() AS full_count
                FROM fts_index fts
                JOIN files f ON f.id = fts.file_id
                WHERE fts_index MATCH ?
                ORDER BY rank
                LIMIT ? OFFSET ?
                """,
                (query, limit, offset),
            )

            results = []
            full_count = 0
            for row in c.fetchall():
                if full_count == 0:
                    full_count = row[4]
                results.append(
                    {
                        "file": row[0],
                        "sheet": row[1],
                        "row": row[2] + 1,
                        "snippet": row[3],
                    }
                )

        return jsonify(results=results, count=full_count)
    except Exception:
        app.logger.exception("搜索失败")
        return jsonify(results=[], count=0, error="internal error"), 500
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)