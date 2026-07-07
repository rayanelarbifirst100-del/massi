from datetime import datetime
from sqlalchemy import create_engine, Column,or_, String, Text, DateTime, Integer, Float, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship
import os
from pathlib import Path
import json

# Place this near your DATABASE_URL configuration
UPLOAD_DIR_PROFILE = Path("images/profile")
UPLOAD_DIR_PROFILE.mkdir(parents=True, exist_ok=True)

UPLOAD_DIR_PRODUCTS = Path("images/products")
UPLOAD_DIR_PRODUCTS.mkdir(parents=True, exist_ok=True)


UPLOAD_DIR_IDENTITIES = Path("images/identities")  
UPLOAD_DIR_IDENTITIES.mkdir(parents=True, exist_ok=True)

# 1. DATABASE CONFIGURATION
DATABASE_URL = "mysql+pymysql://user:pass@localhost/kiraa_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def delete_old_file(url: str):
  """Parses the URL and deletes the file from the local directory if it exists."""
  if not url:
    return
  try:
    # Example URL: /images/profile/uuid.jpg -> Target: static/images/profile/uuid.jpg
    disk_path = Path("."+url) # remove leading slash
    # Convert the URL path to the actual disk path
    # Assuming your structure is static/images/...
    #disk_path = Path(".") / relative_path
    print(disk_path)
    if disk_path.exists():
      os.remove(disk_path)
      print(f"Cleanup: Deleted old file {disk_path}")
  except Exception as e:
    print(f"Cleanup Error: {e}")


class Base(DeclarativeBase):
  pass

# 2. MODELS
class User(Base):
  __tablename__ = "users"
  # Set 'id' as the internal PK, 'authorId' as a unique public identifier
  id = Column(Integer, primary_key=True, autoincrement=True) # Primary
  authorId = Column(String(50), unique=True, nullable=True) # NOT Primary
  name = Column(String(100))
  email = Column(String(100), unique=True)
  bio = Column(Text,nullable=True)
  image = Column(String(255),nullable=True)
  password = Column(String(255))
  phone = Column(String(20))
  USER_ID=Column(String(255),nullable=True)
  account_status = Column(String(20), default="enabled")
  socials = Column(JSON,nullable=True) # Changed to JSON type for native support
  account_creation = Column(DateTime, default=datetime.utcnow)
 
  # Optional: Relationship to see user products
  products = relationship("Product", backref="owner")

class Reports(Base):
  __tablename__ = "reports"
  id = Column(Integer, primary_key=True, autoincrement=True) # Primary
  reports = Column(String(255), nullable=True) # NOT Primary
  reports = Column(String(255), nullable=True) # NOT Primary
  authorImage = Column(String(255), nullable=True) # NOT Primary
  reports_title = Column(String(255), nullable=True) # NOT Primary
  authorId = Column(String(255), nullable=True) # NOT Primary


class Cards(Base):
  __tablename__ = "cards"
  id = Column(Integer, primary_key=True, autoincrement=True) # Primary
  name = Column(String(255), nullable=True) # NOT Primary
  authorid = Column(String(255), nullable=True) # NOT Primary
  number = Column(String(255), nullable=True) # NOT Primary
  expire_date = Column(String(255), nullable=True) # NOT Primary

class Categories(Base):
  __tablename__ = "Categories"
  id = Column(Integer, primary_key=True, autoincrement=True) # Primary
  category = Column(String(255), nullable=True) # NOT Primary


class Admin(Base):
  __tablename__ = "admin"
  id = Column(Integer, primary_key=True, autoincrement=True) # Primary
  username = Column(String(255), nullable=True) # NOT Primary
  password = Column(String(255), nullable=True) # NOT Primary




class Product(Base):
  __tablename__ = "products"
  id = Column(Integer, primary_key=True, autoincrement=True)
  title = Column(String(255))
  price = Column(String(50))
  category = Column(String(50))
  city = Column(String(50))
  rating = Column(Float, default=0)
  description = Column(Text)
  authorId = Column(String(50), ForeignKey("users.authorId"))
  images = Column(JSON) # Changed to JSON
  product_creation = Column(DateTime, default=datetime.utcnow)
  product_status = Column(String(20), default="disabled")


class Order(Base):
  __tablename__ = "orders"
  id = Column(Integer, primary_key=True, autoincrement=True)
  created_at = Column(DateTime, default=datetime.utcnow)
  status = Column(String(20), default="pending") # pending, completed, cancelled
  title = Column(String(255))
  price = Column(String(50))
  authorId = Column(String(50), ForeignKey("users.authorId"))
  productUrl = Column(String(255))
  productId = Column(Integer)
  customer_name = Column(String(255))
  customer_contact = Column(String(255))
  customer_id = Column(String(255),nullable=True)
  start_date = Column(String(50))
  end_date = Column(String(50)) 
  payment_method = Column(String(50))
  baridi_name = Column(String(255), nullable=True)
  baridi_rip = Column(String(50), nullable=True)
  notes = Column(Text, nullable=True)



# Create tables
Base.metadata.create_all(bind=engine)

# 3. CLEAN GENERIC CRUD LOGIC
def create_item(model, data):
  with SessionLocal() as db:
    try:
      # We don't need json.dumps if we use Column(JSON)
      new_item = model(**data)
      db.add(new_item)
      db.commit()
      db.refresh(new_item)
      return new_item
    except Exception as e:
      db.rollback()
      print(f"Error: {e}")
      return None

# def read_item(model, lookup_val):
#   with SessionLocal() as db:
#     # Smart Lookup: Checks authorId for Users, id for Products/Orders
#     if model == User:
#       return db.query(User).filter(User.authorId == lookup_val).first()
#     elif model == Order:
#       return db.query(Order).filter(or_(Order.id == lookup_val,Order.authorId == lookup_val)).first()
#     else:
#       return db.query(model).filter(model.id == lookup_val).first()

def read_item(model, lookup_val):
    with SessionLocal() as db:
        if model == User:
            return db.query(User).filter(User.authorId == lookup_val).first()
        elif model == Order:
            if isinstance(lookup_val, str) and not lookup_val.isdigit():
                return db.query(Order).filter(Order.authorId == lookup_val).all()
            else:
                return db.query(Order).filter(Order.id == lookup_val).first()
        else:
            return db.query(model).filter(model.id == lookup_val).first()


def patch_item(model, lookup_val, update_data):
    with SessionLocal() as db:
        try:
            if model == User:
                query = db.query(User).filter(User.authorId == lookup_val)
            elif model == Order:
                query = db.query(Order).filter(Order.id == lookup_val)
            else:
                query = db.query(model).filter(model.id == lookup_val)
                
            if query.first():
                query.update(update_data)
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            print(f"Database error during patch operation: {e}") # Optional: for debugging backend logs
            return False

def delete_item(model, lookup_val):
  with SessionLocal() as db:
    item = read_item(model, lookup_val)
    if item:
      db.delete(item)
      db.commit()
      return True
    return False





# 3. CRUD FUNCTIONS
def create_user(user_data):
  with SessionLocal() as db:
    try:
      # 1. Handle JSON serialization for socials
      if "socials" in user_data and isinstance(user_data["socials"], dict):
        user_data["socials"] = json.dumps(user_data["socials"], ensure_ascii=False)
     
      # 2. Create object
      new_user = User(**user_data)
      db.add(new_user)
     
      # 3. Flush to get the 'id' from MySQL
      db.flush()
     
      # 4. Generate and MANUALLY assign the authorId
      generated_author_id = f"user_{new_user.name.lower().replace(' ', '')}_{new_user.id}"
      new_user.authorId = generated_author_id
     
      print(f"DEBUG: Generated ID is {new_user.authorId}")
      # 5. Commit and EXPLICITLY refresh
      db.commit()
      db.refresh(new_user)
     
      # 6. DOUBLE CHECK: If refresh didn't grab it, force it manually for the response
      if not new_user.authorId:
        new_user.authorId = generated_author_id
       
      return new_user
     
    except Exception as e:
      db.rollback()
      print(f"Error: {e}")
      return None




def read_user(author_id):
    """READ"""
    with SessionLocal() as db:
        user = db.query(User).filter(or_(User.id == author_id, User.authorId == author_id, User.email == author_id)).first()
        
        if user and user.socials:
            # بما أن النوع في الموديل هو JSON، فإن user.socials قد يكون dict بالفعل
            if isinstance(user.socials, str):
                user.socials_dict = json.loads(user.socials)
            else:
                user.socials_dict = user.socials
        return user


def patch_user(author_id, update_data):
    """PATCH"""
    with SessionLocal() as db:
        try:
            user_query = db.query(User).filter(or_(User.id == author_id, User.authorId == author_id))
            print(update_data)
            if user_query.first():
                if "socials" in update_data:
                    if isinstance(update_data["socials"], str):

                        try:
                            update_data["socials"] = json.loads(update_data["socials"])
                            print(update_data)
                        except:
                            pass
                user_query.update(update_data)
                db.commit()
                print(f"Successfully updated user: {author_id}")
                return True
            return False

        except Exception as e:
            db.rollback()
            print(f"Error: {e}")
            return False


def delete_user(author_id):
  """DELETE"""
  with SessionLocal() as db:
    try:
      user = db.query(User).filter(or_(User.id == author_id, User.authorId == author_id)).first()
      if user:
        db.delete(user)
        db.commit()
        print(f"Successfully deleted user: {author_id}")
        return True
      return False
    except Exception as e:
      db.rollback()
      print(f"Error: {e}")

def verify_user_login(email, password):
  """Checks credentials and returns the user if valid"""
  with SessionLocal() as db:
    # 1. Find user by email
    user = db.query(User).filter(User.email == email).first()
   
    # 2. Check if user exists and password matches
    # Note: In production, you should use password hashing (e.g., bcrypt)
    if user and user.password == password:
      return user
   
    return None



## //////////////// products /////////////////////////
def read_products_range(start: int = 0, count: int = 10):
  with SessionLocal() as db:
    try:
      products = db.query(Product).offset(start).limit(count).all()
      return products
    except Exception as e:
      print(f"Error reading products range: {e}")
      return []

def read_products_by_author(author_id: str):
  """Fetches all products created by a specific author"""
  with SessionLocal() as db:
    # We use .all() because one author can have multiple products
    products = db.query(Product).filter(Product.authorId == author_id).all()
    return products


def read_orders_by_status(status_val: str):
    with SessionLocal() as db:
        # Returns a list of all orders matching the status
        return db.query(Order).filter(Order.status == status_val).all()
        


#reports and cards:


def read_cards_by_author(author_id: str):
    with SessionLocal() as db:
        return db.query(Cards).filter(Cards.authorid == author_id).all()

def read_all_reports():
    with SessionLocal() as db:
        return db.query(Reports).all()

def read_all_categories():
    with SessionLocal() as db:
        return db.query(Categories).all()

def delete_category_item(category_id: int):
    with SessionLocal() as db:
        try:
            item = db.query(Categories).filter(Categories.id == category_id).first()
            if item:
                db.delete(item)
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            print(f"Error deleting category: {e}")
            return False

def delete_user_cascade(author_id: str):
    with SessionLocal() as db:
        try:
            user = db.query(User).filter(or_(User.id == author_id, User.authorId == author_id)).first()
            if not user:
                return False
            target_id = user.authorId
            db.query(Product).filter(Product.authorId == target_id).delete()
            db.query(Order).filter(Order.authorId == target_id).delete()
            db.query(Reports).filter(Reports.authorId == target_id).delete()
            db.query(Cards).filter(Cards.authorid == target_id).delete()
            db.delete(user)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            print(f"Error deleting user cascade: {e}")
            return False



# # 4. EXECUTION EXAMPLE
# if __name__ == "__main__":

 
#  #//////////////////// user part //////////////////////
#  #//////////////////// user part //////////////////////
#  #//////////////////// user part //////////////////////
#  data = {
#    "name": "rayane",
#    "authorId": "user_karim_001",
#    "bio": "مرحباً بكم في متجري الخاص!",
#    "email": "rayande.dev@kiraa.dz",
#    "image": "https://i.pravatar.cc/150?u=rayane",
#    "password": "securepassword123",
#    "phone": "0555 11 22 33",
#    "account_status": "enabled",
#    "socials": {"facebook": "https://facebook.com/rayane"}
#  }
#  #create_user(data)
#  user_record = read_user("user_amine_001")
#  # display_data = {
#  #  "authorId": user_record.authorId,
#  #  "name": user_record.name,
#  #  "email": user_record.email,
#  #  "bio": user_record.bio,
#  #  "phone": user_record.phone,
#  #  "status": user_record.account_status,
#  #  "socials": json.loads(user_record.socials) if isinstance(user_record.socials, str) else user_record.socials,
#  #  "created_at": str(user_record.account_creation)
#  # }
#  # print(display_data)
#  #patch_user("user_amine_001", {"phone": "0770 00 11 22"})

 
#  #//////////////////// product part //////////////////////
#  #//////////////////// product part //////////////////////
#  #//////////////////// product part //////////////////////

#  product_data = {
#    "title": "سيارة Dacia Stepway 2023",
#    "price": "7000 دج/يوم",
#    "category": "سيارات",
#    "city": "الجزائر",
#    "rating": 0,
#    "description": "سيارة مريحة واقتصادية، نظيفة جداً.",
#    "authorId": "user_amine_001",
#    "images": [
#      "https://images.unsplash.com/photo-1541899481282-d53bffe3c35d",
#      "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf"
#    ]
#  }
 
#  print("--- Testing Product ---")
#  create_item(Product, product_data)
#  read_item(Product, 1) # Read product with ID 1

 
#  #//////////////////// order part //////////////////////
#  #//////////////////// order part //////////////////////
#  #//////////////////// order part //////////////////////

#  order_data = {
#    "id": "ORD-1001",
#    "date": "2024-05-23",
#    "status": "pending",
#    "title": "سيارة Dacia Stepway 2023",
#    "price": "7000 دج/يوم",
#    "authorId": "user_amine_001",
#    "productUrl": "/products?id=1"
#  }

 
#  print("\n--- Testing Order ---")
#  create_item(Order, order_data)
#  read_item(Order, "ORD-1001")
 
#  # Example Patch
#  patch_item(Order, "ORD-1001", {"status": "completed"})