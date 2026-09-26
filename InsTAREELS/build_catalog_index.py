"""Create a disposable fast-lookup index beside the user-readable JSON catalog."""
import json
from pathlib import Path
import sqlite3
from jarvis.catalog import key

BASE = Path(__file__).resolve().parent


def build(base=BASE):
    base = Path(base)
    source = base / "file_catalog.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    temporary = base / "file_catalog.building.sqlite3"
    if temporary.exists():
        temporary.unlink()
    with sqlite3.connect(temporary) as connection:
        connection.execute("CREATE TABLE paths (kind TEXT, path TEXT, name TEXT, stem TEXT, parent TEXT)")
        for kind, paths in (("file", data["files"]), ("folder", data["folders"])):
            def rows():
                for value in paths:
                    path = Path(value)
                    yield kind, value, key(path.name), key(path.stem), key(path.parent.name)
            connection.executemany("INSERT INTO paths VALUES (?,?,?,?,?)", rows())
        connection.execute("CREATE INDEX by_name ON paths(kind,name)")
        connection.execute("CREATE INDEX by_stem ON paths(kind,stem)")
        connection.execute("CREATE INDEX by_path ON paths(kind,path COLLATE NOCASE)")
        connection.execute("CREATE TABLE metadata (size INTEGER, mtime INTEGER)")
        stat = source.stat()
        connection.execute("INSERT INTO metadata VALUES (?,?)", (stat.st_size, stat.st_mtime_ns))
    connection.close()
    temporary.replace(base / "file_catalog.sqlite3")
    print("Fast file and folder lookup index ready.", flush=True)


if __name__ == "__main__":
    build()
