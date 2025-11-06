import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from typing import List
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from schemas import Order, OrderResponse
from database import create_document, get_documents

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Helmet Orders API ready"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        from database import db
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else (os.getenv("DATABASE_NAME") or "Unknown")
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


def send_email(subject: str, to_email: str, html_body: str) -> bool:
    """Send an email using SMTP credentials from environment variables.
    Returns True if sent, False otherwise.
    Required envs: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, FROM_EMAIL
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    from_email = os.getenv("FROM_EMAIL", smtp_user or "noreply@example.com")

    if not (smtp_host and smtp_user and smtp_pass):
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = from_email
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, [to_email], msg.as_string())
        return True
    except Exception:
        return False


@app.post("/orders", response_model=OrderResponse)
def create_order(order: Order):
    """Create a helmet order, save to DB, push to Google Sheets, and notify admin/client via email."""
    # 1) Save to database
    try:
        order_id = create_document("order", order)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    # 2) Push to Google Sheets via Apps Script Webhook (optional)
    sheets_status = "skipped"
    sheets_webhook = os.getenv("SHEETS_WEBHOOK_URL")
    if sheets_webhook:
        payload = {
            "order_id": order_id,
            "customer_name": order.customer_name,
            "email": order.email,
            "phone": order.phone,
            "address": order.address,
            "model": order.model,
            "size": order.size,
            "quantity": order.quantity,
            "notes": order.notes,
        }
        try:
            r = requests.post(sheets_webhook, json=payload, timeout=10)
            if r.ok:
                sheets_status = "sent"
            else:
                sheets_status = f"error:{r.status_code}"
        except Exception:
            sheets_status = "error"

    # 3) Notifications via Email (optional)
    admin_email = os.getenv("ADMIN_EMAIL")
    notify_status = []

    admin_html = f"""
    <h2>Pesanan Helm Baru</h2>
    <p><strong>Nama:</strong> {order.customer_name}</p>
    <p><strong>Email:</strong> {order.email or '-'} | <strong>Telp:</strong> {order.phone}</p>
    <p><strong>Alamat:</strong> {order.address}</p>
    <p><strong>Model:</strong> {order.model} | <strong>Ukuran:</strong> {order.size} | <strong>Qty:</strong> {order.quantity}</p>
    <p><strong>Catatan:</strong> {order.notes or '-'} </p>
    <p><strong>Order ID:</strong> {order_id}</p>
    """

    if admin_email:
        sent = send_email("Pesanan Helm Baru", admin_email, admin_html)
        notify_status.append(f"admin:{'sent' if sent else 'failed'}")

    if order.email:
        client_html = f"""
        <h2>Terima kasih, {order.customer_name}!</h2>
        <p>Pesanan helm Anda sudah kami terima.</p>
        <p>Detail pesanan:</p>
        <ul>
            <li>Model: {order.model}</li>
            <li>Ukuran: {order.size}</li>
            <li>Jumlah: {order.quantity}</li>
        </ul>
        <p>Order ID: {order_id}</p>
        <p>Kami akan segera menghubungi Anda untuk konfirmasi.</p>
        """
        sent = send_email("Konfirmasi Pesanan Helm", order.email, client_html)
        notify_status.append(f"client:{'sent' if sent else 'failed'}")

    return OrderResponse(
        id=order_id,
        status="created",
        sheet_status=sheets_status,
        notification_status=",".join(notify_status) if notify_status else "skipped"
    )


@app.get("/orders")
def list_orders(limit: int = 20):
    try:
        docs = get_documents("order", limit=limit)
        # Convert ObjectId to str if present
        for d in docs:
            if "_id" in d:
                d["_id"] = str(d["_id"])
        return {"items": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching orders: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
