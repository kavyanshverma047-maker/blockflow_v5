from .ledger import create_reserve, release_reserve, post_transaction
from decimal import Decimal
def deposit(user_id:int, currency:str, amount):
    # deposit increases user's available via a credit entry; we model source as external: 'bank'
    entries = [
        {'account': f'user:{user_id}:{currency}:available', 'amount': str(Decimal(amount))},
        {'account': f'external:bank:{currency}', 'amount': str(-Decimal(amount))}
    ]
    return post_transaction(entries, ref='deposit')

def reserve(user_id:int, currency:str, amount):
    return create_reserve(user_id, currency, amount)

def release(user_id:int, currency:str, amount):
    return release_reserve(user_id, currency, amount)

def settle(from_user:int, to_user:int, currency:str, amount, fee=0):
    return post_transaction([
        {'account': f'user:{from_user}:{currency}:reserved', 'amount': str(-Decimal(amount))},
        {'account': f'user:{to_user}:{currency}:available', 'amount': str(Decimal(amount) - Decimal(fee))},
        {'account': f'platform:fees:{currency}', 'amount': str(Decimal(fee))}
    ], ref='settle')
