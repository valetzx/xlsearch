import sqlite3
from config import DB_PATH

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 创建元数据表
    c.execute('''CREATE TABLE IF NOT EXISTS files
                 (id INTEGER PRIMARY KEY, 
                  path TEXT UNIQUE, 
                  last_modified REAL)''')
    
    # 创建全文搜索虚拟表 (FTS5)
    c.execute('''CREATE VIRTUAL TABLE IF NOT EXISTS fts_index USING fts5
                 (file_id, sheet_name, row_index, content, tokenize="porter unicode61")''')
    
    conn.commit()
    conn.close()

def get_conn():
    return sqlite3.connect(DB_PATH)