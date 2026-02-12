import sqlite3


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS ridership (
            route TEXT NOT NULL,
            date TEXT NOT NULL,
            daytype TEXT NOT NULL,
            rides INTEGER NOT NULL,
            PRIMARY KEY (route, date)
        );

        CREATE TABLE IF NOT EXISTS vehicle_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collected_at TEXT NOT NULL,
            vid TEXT NOT NULL,
            tmstmp TEXT NOT NULL,
            route TEXT NOT NULL,
            direction TEXT,
            destination TEXT,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            heading INTEGER,
            speed INTEGER,
            pdist INTEGER,
            pattern_id TEXT,
            delayed BOOLEAN DEFAULT FALSE
        );

        CREATE INDEX IF NOT EXISTS idx_vp_route_time
            ON vehicle_positions(route, collected_at);
        CREATE INDEX IF NOT EXISTS idx_vp_vid_time
            ON vehicle_positions(vid, collected_at);

        CREATE TABLE IF NOT EXISTS stop_arrivals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route TEXT NOT NULL,
            direction TEXT NOT NULL,
            stop_id TEXT NOT NULL,
            vid TEXT NOT NULL,
            arrival_time TEXT NOT NULL,
            pdist_at_arrival INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_arrivals_route_stop
            ON stop_arrivals(route, stop_id, arrival_time);

        CREATE TABLE IF NOT EXISTS reference_stops (
            route TEXT NOT NULL,
            direction TEXT NOT NULL,
            stop_id TEXT NOT NULL,
            stop_name TEXT,
            pdist INTEGER,
            PRIMARY KEY (route, direction)
        );
        """
    )


def insert_ridership(
    conn: sqlite3.Connection,
    route: str,
    date: str,
    daytype: str,
    rides: int,
) -> None:
    conn.execute(
        """
        INSERT INTO ridership (route, date, daytype, rides)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(route, date) DO UPDATE SET
            daytype = excluded.daytype,
            rides = excluded.rides
        """,
        (route, date, daytype, rides),
    )
    conn.commit()


def insert_vehicle_position(
    conn: sqlite3.Connection,
    *,
    collected_at: str,
    vid: str,
    tmstmp: str,
    route: str,
    direction: str | None = None,
    destination: str | None = None,
    lat: float,
    lon: float,
    heading: int | None = None,
    speed: int | None = None,
    pdist: int | None = None,
    pattern_id: str | None = None,
    delayed: bool = False,
) -> None:
    conn.execute(
        """
        INSERT INTO vehicle_positions
            (collected_at, vid, tmstmp, route, direction, destination,
             lat, lon, heading, speed, pdist, pattern_id, delayed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            collected_at, vid, tmstmp, route, direction, destination,
            lat, lon, heading, speed, pdist, pattern_id, delayed,
        ),
    )
    conn.commit()


def insert_stop_arrival(
    conn: sqlite3.Connection,
    *,
    route: str,
    direction: str,
    stop_id: str,
    vid: str,
    arrival_time: str,
    pdist_at_arrival: int | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO stop_arrivals
            (route, direction, stop_id, vid, arrival_time, pdist_at_arrival)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (route, direction, stop_id, vid, arrival_time, pdist_at_arrival),
    )
    conn.commit()


def insert_reference_stop(
    conn: sqlite3.Connection,
    *,
    route: str,
    direction: str,
    stop_id: str,
    stop_name: str | None = None,
    pdist: int | None = None,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO reference_stops
            (route, direction, stop_id, stop_name, pdist)
        VALUES (?, ?, ?, ?, ?)
        """,
        (route, direction, stop_id, stop_name, pdist),
    )
    conn.commit()


def _rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def query_ridership(
    conn: sqlite3.Connection,
    routes: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    query = "SELECT * FROM ridership WHERE 1=1"
    params: list = []

    if routes:
        placeholders = ",".join("?" for _ in routes)
        query += f" AND route IN ({placeholders})"
        params.extend(routes)
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    query += " ORDER BY route, date"
    cursor = conn.execute(query, params)
    return _rows_to_dicts(cursor)


def query_vehicle_positions(
    conn: sqlite3.Connection,
    route: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    query = "SELECT * FROM vehicle_positions WHERE 1=1"
    params: list = []

    if route:
        query += " AND route = ?"
        params.append(route)
    if start_time:
        query += " AND collected_at >= ?"
        params.append(start_time)
    if end_time:
        query += " AND collected_at <= ?"
        params.append(end_time)

    query += " ORDER BY collected_at"
    cursor = conn.execute(query, params)
    return _rows_to_dicts(cursor)


def query_stop_arrivals(
    conn: sqlite3.Connection,
    route: str,
    stop_id: str,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    query = "SELECT * FROM stop_arrivals WHERE route = ? AND stop_id = ?"
    params: list = [route, stop_id]

    if start_time:
        query += " AND arrival_time >= ?"
        params.append(start_time)
    if end_time:
        query += " AND arrival_time <= ?"
        params.append(end_time)

    query += " ORDER BY arrival_time"
    cursor = conn.execute(query, params)
    return _rows_to_dicts(cursor)
