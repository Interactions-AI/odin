import os
import sqlalchemy as sql
import sqlalchemy.orm as sql_orm
from sqlalchemy.ext.declarative import declarative_base

import bcrypt

SECURITY_PASSWORD_SALT = os.environ.get('ODIN_SALT').encode("UTF-8")


Base = declarative_base()


class Dao:

    def __init__(self, dbname='odin_db',
                 uri=None,
                 dbtype='postgresql',
                 dbhost='localhost',
                 dbport=None,
                 user=None,
                 passwd=None,
                 odin_root_user=None,
                 odin_root_passwd=None,
                 **kwargs):

        if uri is None:
            host_fmt = '{}:{}'.format(dbhost, dbport) if dbport else dbhost
            user_fmt = user if passwd is None else '{}:{}'.format(user, passwd)
            uri = '{}://{}@{}/{}'.format(dbtype, user_fmt, host_fmt, dbname)
        self._connect(uri)
        if odin_root_user and odin_root_passwd:
            session = self.Session()
            user = session.query(User).filter(User.username == odin_root_user).first()
            if not user:
                user = User(username=odin_root_user, password=odin_root_passwd)
                session.add(user)
                session.commit()
            else:
                user.password = odin_root_passwd
                session.commit()

    def _connect(self, uri):
        self.engine = sql.create_engine(uri, echo=False, paramstyle='format', pool_size=100)
        Base.metadata.create_all(self.engine)
        self.Session = sql_orm.sessionmaker(bind=self.engine)

    def get_user(self, username):
        session = self.Session()
        user = session.query(User).filter(User.username == username).first()
        return user

    def get_users(self, q=None):
        session = self.Session()
        if not q:
            return session.query(User).all()
        return session.query(User).filter(User.username.ilike(f'%{q}%')).all()

    def create_user(self, object):
        session = self.Session()
        user = session.query(User).filter(User.username == object.username).first()
        if user:
            raise Exception(f"User {user.username} already exists!")
        user = User(username=object.username, password=object.password, firstname=object.firstname, lastname=object.lastname)
        session.add(user)
        session.commit()
        return user

    def update_user(self, object):
        session = self.Session()
        user = session.query(User).filter(User.username == object.username).first()
        if not user:
            raise Exception(f"No such user {object.username}!")

        if object.firstname:
            user.firstname = object.firstname
        if object.lastname:
            user.lastname = object.lastname
        if object.password:
            user.password = object.password
        session.commit()
        return user

    def delete_user(self, username):
        session = self.Session()
        user = session.query(User).filter(User.username == username).first()
        if not user:
            raise Exception(f"No such user {username}!")
        session.delete(user)
        session.commit()
        return user

    def create_session(self):
        return self.Session()



class JobRef(Base):
    __tablename__ = 'job_refs'
    id = sql.Column(sql.Integer, primary_key=True)
    # This is going to be the name in the jobs_db
    handle = sql.Column(sql.String(255), unique=True)
    user_id = sql.Column(sql.Integer, sql.ForeignKey('users.id'))
    user = sql_orm.relationship("User", back_populates="job_refs")


class User(Base):

    __tablename__ = 'users'
    id = sql.Column(sql.Integer, primary_key=True)
    username = sql.Column(sql.String(255), unique=True)
    firstname = sql.Column(sql.String(255), unique=True)
    lastname = sql.Column(sql.String(255), unique=True)
    password_hash = sql.Column(sql.LargeBinary(128))
    job_refs = sql_orm.relationship('JobRef', back_populates='user')

    @property
    def password(self):
        raise AttributeError('password not readable')

    @password.setter
    def password(self, password):
        password_bytes = bytes(password, encoding='utf-8')
        self.password_hash = bcrypt.hashpw(password_bytes, SECURITY_PASSWORD_SALT)

    def authenticate(self, password) -> bool:
        """Authenticate the user

        :param password: The user password
        :return:
        """
        password_bytes = bytes(password, encoding='utf-8')
        hashed = bcrypt.hashpw(password_bytes, SECURITY_PASSWORD_SALT)
        return hashed == self.password_hash

