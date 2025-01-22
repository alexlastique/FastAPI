import hashlib, jwt
from fastapi import FastAPI, Depends, HTTPException
from sqlmodel import Session, create_engine, SQLModel, Field, select
from pydantic import BaseModel
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pathlib import Path
from user import User
from compte import Compte
import logging

app = FastAPI()

logging.basicConfig(level=logging.INFO)

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)

def create_db_and_tables():
    database = Path("../database.db")
    if not database.is_file():
        SQLModel.metadata.create_all(engine)

secret_key = "very_secret_key"
algorithm = "HS256"

bearer_scheme = HTTPBearer()

def get_user(authorization: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    return jwt.decode(authorization.credentials, secret_key, algorithms=[algorithm])

def generate_token(user: User):
    id = {"id": user.id, "email": user.email}
    return jwt.encode(id, secret_key, algorithm=algorithm)

def get_session():
    with Session(engine) as session:
        yield session

@app.post("/account_add/")
def create_compte(body: Compte, session = Depends(get_session), userid=Depends(get_user)) -> Compte:
    compte = Compte(nom=body.nom , iban=body.iban , userId=userid["id"])
    session.add(compte)
    session.commit()
    session.refresh(compte)
    return compte


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


soldeCompte = 90000
@app.get("/")
def read_root():
    return {"message": "Bienvenue sur l'API BackFrontDevops"}

@app.get("/users/")
def read_users(session = Depends(get_session)):
    users = session.exec(select(User)).all()
    return users

@app.post("/register")
async def register(email: str, mdp: str, session=Depends(get_session)):
    query = select(User).where(User.email == email)
    users = session.exec(query).all()
    if users:
        return {"message": "L'email est déjà utilisé"}
    if not mdp:
        return {"message": "Le mot de passe est requis"}
    
    mdp_hash = hashlib.sha256(mdp.encode()).hexdigest()
    user = User(email=email, mdp=mdp_hash)
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"message": "Utilisateur créé avec succès"}

@app.post("/login")
def login(user: User, session=Depends(get_session)):
    query = select(User).where(User.email == user.email, User.mdp == hashlib.sha256(user.mdp.encode()).hexdigest())
    user = session.exec(query).first()
    if not user:
        raise HTTPException(status_code=404, detail="Email ou mdp incorrect")

    return {"token": generate_token(user)}

@app.get("/me")
def me(user=Depends(get_user), session=Depends(get_session)):
    query = select(Compte).where(Compte.userId == user["id"])
    compte = session.exec(query).all()
    return {"user": user, "Nombre de compte": len(compte)}

@app.post("/deposit")
async def deposit(amount: float, iban_dest : str, session=Depends(get_session), user=Depends(get_user)):
    if amount<=0:
        return {"message": "Le montant doit être supérieur à zéro"}
    
    query = select(Compte.iban).where(Compte.userId == user["id"])
    listIban = session.exec(query).all()

    if iban_dest not in listIban:
        return {"message": "Compte introuvable"}
    
    query = select(Compte).where(Compte.iban == iban_dest)
    compte = session.exec(query).first()
    compte.solde += amount
    session.commit()
    session.refresh(compte)

    return {"message": f"Dépot de {amount} euros réussi. Il vous reste {compte.solde}."}



# @app.post("/send_money")
# async def send_money(amount: float, compte: str):
#     global soldeCompte
#     if amount<=0:
#         return {"message": "Le montant doit être supérieur à zéro"}
#     if compte=="backfrontdevops":
#         return {"message": "Vous ne pouvez pas transférer de l'argent à votre propre compte"}
#     if amount>soldeCompte:
#         return {"message": "Le montant transféré dépasse le solde du compte"}
#     if compte not in ["test"]:
#         return {"message": "Le compte cible est inaccessible"}
#     soldeCompte -= amount
#     return {"message": f"Transfert de {amount} euros vers {compte} réussi. Il vous reste {soldeCompte}."}

@app.get("/compte/{iban}")
async def get_compte(iban: str, user=Depends(get_user), session=Depends(get_session)):
    query = select(Compte.iban).where(Compte.userId == user["id"])
    listIban = session.exec(query).all()
    if iban not in listIban:
        return {"message": "Compte introuvable"}
    query = select(Compte).where(Compte.iban == iban)
    compte = session.exec(query).first()
    transactions_on_going = []
    transactions_historique = [
        {"date": "2022-01-01", "montant": 5000, "type": "Débit"},
        {"date": "2022-01-02", "montant": 2000, "type": "Débit"},
        {"date": "2022-01-03", "montant": 300, "type": "Débit"},
        {"date": "2022-01-04", "montant": 1000, "type": "Crédit"}
    ]
    
    return {
        "name": compte.nom,
        "date_creation": compte.dateCreation,
        "iban": compte.iban,
        "user": compte.userId,
        "solde": compte.solde,
        "transactions_on_going": transactions_on_going,
        "transactions_historique": transactions_historique
        }
