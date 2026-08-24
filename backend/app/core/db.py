from sqlmodel import Session, create_engine

from app.core.config import settings
from app.models import UserCreate
from app.repositories.user_repository import UserRepository
from app.services.user_service import new_user

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    users = UserRepository(session)
    if users.find_by_email(settings.FIRST_SUPERUSER) is None:
        # Deliberately not UserService.create_user: the first superuser must
        # not be emailed their own bootstrap password.
        users.save(
            new_user(
                UserCreate(
                    email=settings.FIRST_SUPERUSER,
                    password=settings.FIRST_SUPERUSER_PASSWORD,
                    is_superuser=True,
                )
            )
        )
