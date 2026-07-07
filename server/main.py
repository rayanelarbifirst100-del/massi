import uvicorn
from fastapi import FastAPI, HTTPException, Body , UploadFile, File , Form
from typing import Dict, Any,List,Optional
import shutil
import uuid  # For unique filenames
from fastapi.staticfiles import StaticFiles
from functions import UPLOAD_DIR_PROFILE # Import the path we defined
from functions import UPLOAD_DIR_PRODUCTS # Import the path we defined
from functions import UPLOAD_DIR_IDENTITIES # Import the path we defined

# Import your models and functions from functions.py
from functions import SessionLocal # Ensure SessionLocal is imported

from functions import (
    User, Product, Order, Cards, Reports,Admin,
    create_item, read_item, patch_item, delete_item,verify_user_login,read_products_range,
    create_user, read_user, patch_user, delete_user,delete_old_file,read_products_by_author,
    read_orders_by_status,read_cards_by_author,read_all_reports
)
from fastapi.middleware.cors import CORSMiddleware
from google.oauth2 import id_token
from google.auth.transport import requests
from pydantic import BaseModel # Added for schema structural tracking

app = FastAPI(
    title="Kiraa API",
    description="API for managing Users, Products, and Orders with smart ID lookup",
    version="2.1.0"
)

class AdminLoginRequest(BaseModel):
    username: str
    password: str
    
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000/",
    "http://0.0.0.0:3000/"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # Allows specific domains
    # allow_origins=["*"],            # Use this if you want to allow EVERYTHING (easier for testing)
    allow_credentials=True,
    allow_methods=["*"],              # Allows all methods (GET, POST, PATCH, DELETE, etc.)
    allow_headers=["*"],              # Allows all headers
    expose_headers=["*"]
)

# This line allows your browser to see the images via URL
app.mount("/images", StaticFiles(directory="images"), name="images")


@app.post("/admin/login")
def api_admin_login(credentials: AdminLoginRequest):
    with SessionLocal() as db:
        # Check both the username and password on the Admin table
        admin_account = (
            db.query(Admin)
            .filter(
                Admin.username == credentials.username,
                Admin.password == credentials.password
            )
            .first()
        )
        
    if not admin_account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="اسم المستخدم أو كلمة المرور غير صحيحة الخاصة بمدير الموقع"
        )
        
    return {
        "status": "success",
        "message": "تم التحقق وصعود لوحة التحكم بنجاح",
        "admin": {
            "username": admin_account.username,
            "authorId": "admin_system_dashboard",  # Matches the ID parameter used across your admin chats
            "role": "editor_administrator"
        }
    }

GOOGLE_CLIENT_ID = "878048146319-gsuhla5gujef7i7nta0e13d7iruqdrol.apps.googleusercontent.com"

@app.post("/auth/google")
def google_auth(data: dict):
    token = data.get("token")
    try:
        # 1. Verify the token with Google
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)

        # 2. Extract user info
        email = idinfo['email']
        name = idinfo.get('name')
        picture = idinfo.get('picture')

        # 3. Check if user exists in your DB
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == email).first()

            if not user:
                # Create a new user if they don't exist
                user_data = {
                    "name": name,
                    "email": email,
                    "image": picture,
                    "password": "GOOGLE_AUTH_USER", # Or leave empty/nullable
                    "phone": "", # Can be updated later
                    "account_status": "enabled"
                }
                user = create_user(user_data) # Uses your existing CRUD function

            return user # Return the user object to the frontend
            
    except ValueError:
        # Invalid token
        return {"error": "Invalid Token"}, 400



@app.get("/users", response_model=List[dict])
def get_users(search: Optional[str] = None):
    with SessionLocal() as db:
        query = db.query(User)
        
        if search:
            # Search by name or email (case-insensitive)
            query = query.filter(
                (User.name.ilike(f"%{search}%")) | 
                (User.email.ilike(f"%{search}%"))
            )
        
        users = query.all()
        
        # Map DB fields to the format the React component expects
        return [
            {
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "image":u.image,
                # Translate internal status to frontend Arabic labels
                "status": "نشط" if u.account_status == "enabled" else "محظور"
            } for u in users
        ]




# 1. Define a request validation schema for incoming data



@app.patch("/users/{user_id}/toggle")
def api_toggle_user_status(user_id: str):
    # 1. Get the user using your existing read_user helper
    user = read_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 2. Determine the new status
    new_status = "disabled" if user.account_status == "enabled" else "enabled"
    
    # 3. Use your existing patch_user helper
    success = patch_user(user_id, {"account_status": new_status})
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update status")
        
    return {
        "id": user_id, 
        "status": "نشط" if new_status == "enabled" else "محظور"
    }

@app.post("/upload-user-image/{author_id}")
async def api_upload_user_image(author_id: str, file: UploadFile = File(...)):
    # 1. Validation & Find User
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    user = read_user(author_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. DELETE THE OLD FILE
    if user.image:
        delete_old_file(user.image)

    # 3. Save the new file
    extension = file.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{extension}"
    file_path = UPLOAD_DIR_PROFILE / unique_filename

    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File system error: {e}")
    finally:
        await file.close()

    # 4. Update DB
    image_url = f"/images/profile/{unique_filename}"
    patch_user(author_id, {"image": image_url})

    return {"status": "success", "url": image_url}


@app.post("/upload-user-identity/{author_id}")
async def api_upload_user_identity(author_id: str, file: UploadFile = File(...)):
    allowed_types = ["image/jpeg", "image/png", "image/jpg", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400, 
            detail="File must be an image (JPEG/PNG) or a PDF document"
        )
    user = read_user(author_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if hasattr(user, 'USER_ID') and user.USER_ID:
        delete_old_file(user.USER_ID)
    extension = file.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{extension}"
    file_path = UPLOAD_DIR_IDENTITIES / unique_filename
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File system error: {e}")
    finally:
        await file.close()
    identity_url = f"/images/identities/{unique_filename}"
    patch_user(author_id, {"USER_ID": identity_url})
    return {"status": "success", "url": identity_url}



@app.post("/update-product-images/{product_id}")
async def api_update_product_images(product_id: int, files: List[UploadFile] = File(...)):
    product = read_item(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # 1. DELETE ALL OLD IMAGES IN THE LIST
    print(product.images)
    if product.images:
        for old_url in product.images:
            delete_old_file(old_url)

    # 2. Save the new bunch
    new_urls = []
    for file in files:
        if not file.content_type.startswith("image/"): continue
        
        unique_filename = f"{uuid.uuid4()}.{file.filename.split('.')[-1]}"
        file_path = UPLOAD_DIR_PRODUCTS / unique_filename

        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        new_urls.append(f"/images/products/{unique_filename}")
        await file.close()

    # 3. Overwrite the DB with the new list (replaces the old one)
    patch_item(Product, product_id, {"images": new_urls})

    return {"status": "success", "all_images": new_urls}




# --- HELPER: SERIALIZATION ---
def format_response(item):
    if not item:
        return None
    
    # Extract columns into a dict
    result = {c.name: getattr(item, c.name) for c in item.__table__.columns}
    
    # Convert datetime objects to ISO strings
    for key, value in result.items():
        if hasattr(value, 'isoformat'):
            result[key] = value.isoformat()
            
    return result

# --- USER ROUTES ---

@app.post("/users", status_code=201)
def api_create_user(data: dict = Body(...)):
    user = create_user(data) 
    if not user:
        raise HTTPException(
            status_code=400, 
            detail="User could not be created. Check if email already exists."
        )
    return {"status": "success", "data": format_response(user)}

@app.get("/users/{author_id}")
def api_get_user(author_id: str):
    # This now works with numeric ID (1) or string authorId (user_rayane_1)
    user = read_user(author_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return format_response(user)

@app.post("/login")
def api_login(data: dict = Body(...)):
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني وكلمة المرور مطلوبان")

    user = verify_user_login(email, password)
    
    if not user:
        raise HTTPException(
            status_code=401, 
            detail="خطأ في البريد الإلكتروني أو كلمة المرور"
        )

    return {
        "status": "success",
        "message": "تم تسجيل الدخول بنجاح",
        "user": format_response(user)
    }

# --- PRODUCT ROUTES ---
@app.get("/products/status/{status_code}")
def api_get_products_by_status(status_code: str):
    with SessionLocal() as db:
        products = db.query(Product).filter(Product.product_status == status_code).all()
        
        if not products:
            return []
        return [format_response(p) for p in products]

@app.post("/products", status_code=201)
def api_create_product(data: dict = Body(...)):
    product = create_item(Product, data)
    if not product:
        raise HTTPException(status_code=400, detail="Product creation failed")
    return {"status": "success", "data": format_response(product)}

@app.get("/products/{product_id}")
def api_get_product(product_id: int):
    product = read_item(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return format_response(product)

@app.get("/products/author/{author_id}")
def api_get_products_by_author(author_id: str):
    # 1. Fetch products using the CRUD function
    products = read_products_by_author(author_id)
    
    # 2. If the list is empty, we still return an empty list [] 
    # (Standard API behavior for filters)
    if not products:
        return []
        
    # 3. Format every product in the list for the JSON response
    return [format_response(p) for p in products]

#/products-range?start=0&limit=10
@app.get("/products-range")
def api_get_products_range(start: int = 0, limit: int = 10):
    products = read_products_range(start, limit)
    return [format_response(p) for p in products]

# --- ORDER ROUTES ---

@app.post("/orders", status_code=201)
def api_create_order(data: dict = Body(...)):
    order = create_item(Order, data)
    if not order:
        raise HTTPException(status_code=400, detail="Order creation failed")
    return {"status": "success", "data": format_response(order)}

@app.get("/orders/{identifier}")
def api_get_orders(identifier: str):
    data = read_item(Order, identifier)
    if not data:
        return []
    if isinstance(data, list):
        return [format_response(order) for order in data]
    return format_response(data)

@app.get("/orders/filter/completed")
def api_get_completed_orders():
    """
    Fetches all orders with status 'completed'
    """
    orders = read_orders_by_status("completed")
    
    if not orders:
        return []
        
    return [format_response(order) for order in orders]


# reports and cards

# Create a new report
@app.post("/reports", status_code=201)
def api_create_report(data: dict = Body(...)):
    report = create_item(Reports, data)
    if not report:
        raise HTTPException(status_code=400, detail="Report creation failed")
    return {"status": "success", "data": format_response(report)}

# Get a single report by ID
@app.get("/reports/{report_id}")
def api_get_report(report_id: int):
    report = read_item(Reports, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return format_response(report)

# Get all reports
@app.get("/reports")
def api_get_all_reports():
    reports = read_all_reports()
    if not reports:
        return []
    return [format_response(r) for r in reports]


# Create a new card
@app.post("/cards", status_code=201)
def api_create_card(data: dict = Body(...)):
    card = create_item(Cards, data)
    if not card:
        raise HTTPException(status_code=400, detail="Card creation failed")
    return {"status": "success", "data": format_response(card)}

# Get a single card by ID
@app.get("/cards/{card_id}")
def api_get_card(card_id: int):
    card = read_item(Cards, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return format_response(card)

# Get all cards registered under a specific author ID
@app.get("/cards/author/{author_id}")
def api_get_cards_by_author(author_id: str):
    cards = read_cards_by_author(author_id)
    if not cards:
        return []
    return [format_response(c) for c in cards]


@app.patch("/cards/{card_id}")
def api_patch_card(card_id: int, data: dict = Body(...)):
    # Safely passes the explicit Cards model directly to your utility function
    success = patch_item(Cards, card_id, data)
    
    if not success:
        raise HTTPException(
            status_code=404, 
            detail=f"Card with ID {card_id} not found or update failed"
        )        
    return {"status": "success", "message": "Card details updated successfully"}

@app.delete("/cards/{card_id}")
def api_delete_card(card_id: int):
    # Safely passes the explicit Cards model directly to your utility function
    success = delete_item(Cards, card_id)
    
    if not success:
        raise HTTPException(
            status_code=404, 
            detail=f"Card with ID {card_id} not found or deletion failed"
        )
        
    return {"status": "success", "message": "Card deleted successfully"}


@app.get("/orders/notification-count/{user_id}")
def api_get_order_notification_count(user_id: str):
    """
    Returns the number of pending orders and the ID of the latest one.
    This is used by the frontend to trigger sounds/popups.
    """
    orders = read_item(Order, user_id)
    if not orders:
        return {"count": 0, "latest_id": None}
    
    # Ensure we are working with a list
    orders_list = orders if isinstance(orders, list) else [orders]
    
    # Filter for pending orders
    pending = [o for o in orders_list if o.status == "pending"]
    
    if not pending:
        return {"count": 0, "latest_id": None}
    
    # Sort to find the newest order ID
    pending.sort(key=lambda x: x.id, reverse=True)
    
    return {
        "count": len(pending),
        "latest_id": pending[0].id,
        "latest_note": pending[0].notes
    }




# --- CATEGORIES ---
from functions import Categories, read_all_categories, delete_category_item, delete_user_cascade

@app.get("/categories")
def api_get_all_categories():
    categories = read_all_categories()
    if not categories:
        return []
    return [format_response(c) for c in categories]

@app.post("/categories", status_code=201)
def api_create_category(data: dict = Body(...)):
    category = create_item(Categories, data)
    if not category:
        raise HTTPException(status_code=400, detail="Category creation failed")
    return {"status": "success", "data": format_response(category)}

@app.patch("/categories/{category_id}")
def api_update_category(category_id: int, data: dict = Body(...)):
    success = patch_item(Categories, category_id, data)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Category with ID {category_id} not found or update failed"
        )
    return {"status": "success", "message": "Category updated successfully"}

@app.delete("/categories/{category_id}")
def api_delete_category(category_id: int):
    success = delete_category_item(category_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Category with ID {category_id} not found or deletion failed"
        )
    return {"status": "success", "message": "Category deleted successfully"}

@app.delete("/users-cascade/{author_id}")
def api_delete_user_cascade(author_id: str):
    success = delete_user_cascade(author_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"User with ID {author_id} not found or deletion failed"
        )
    return {"status": "success", "message": "User and all related data deleted successfully"}

@app.delete("/users/{author_id}")
def api_delete_user_with_deps(author_id: str):
    success = delete_user_cascade(author_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"User with ID {author_id} not found or deletion failed"
        )
    return {"status": "success", "message": "User and all related data deleted successfully"}

# --- GLOBAL UPDATE & DELETE ---

@app.patch("/{collection}/{item_id}")
def api_update_item(collection: str, item_id: str, data: dict = Body(...)):
    coll = collection.lower()
    
    # Use specific patch_user for users to support smart lookup
    if coll == "users":
        success = patch_user(item_id, data)
    elif coll == "products":
        success = patch_item(Product, int(item_id), data)
    elif coll == "orders":
        success = patch_item(Order, item_id, data)
    else:
        raise HTTPException(status_code=400, detail="Invalid collection name")
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found in {collection}")
    
    return {"message": f"Successfully updated {item_id}"}

@app.delete("/{collection}/{item_id}")
def api_delete_item(collection: str, item_id: str):
    coll = collection.lower()
    
    # Use specific delete_user for users to support smart lookup
    if coll == "users":
        success = delete_user(item_id)
    elif coll == "products":
        success = delete_item(Product, int(item_id))
    elif coll == "orders":
        success = delete_item(Order, item_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid collection name")
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
        
    return {"message": f"Successfully deleted {item_id} from {collection}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)