from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.models import Movie


def list_movies(
    db: Session, *, query: str | None, genre: str | None, page: int, limit: int, sort: str
) -> tuple[list[Movie], int]:
    statement = select(Movie).where(Movie.active.is_(True))
    if query:
        escaped = query.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = statement.where(func.lower(Movie.title).like(f"%{escaped}%", escape="\\"))
    if genre:
        statement = statement.where(Movie.genres.contains([genre]))
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    ordering = {
        "title": (Movie.title.asc(), Movie.id.asc()),
        "year_desc": (Movie.release_year.desc().nullslast(), Movie.id.asc()),
        "year_asc": (Movie.release_year.asc().nullslast(), Movie.id.asc()),
    }
    rows = list(db.scalars(statement.order_by(*ordering[sort]).offset((page - 1) * limit).limit(limit)))
    return rows, total
