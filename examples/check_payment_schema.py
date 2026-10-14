from app.schemas.payments import PaymentCreate

payment = {
    "amount": "10",
    "currency": "BVTC",
    "description": "as",
    "webhook_url": "https://example.com",
}


print(PaymentCreate.model_validate(payment))