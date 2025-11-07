import pandas as pd
import numpy as np
import os
import time
import dotenv
import ast
import json
from datetime import datetime, timedelta
from typing import Dict, List, Union
from sqlalchemy import create_engine, Engine
from sqlalchemy.sql import text
from smolagents import OpenAIServerModel, tool, ToolCallingAgent

# Create an SQLite database
db_engine = create_engine("sqlite:///munder_difflin.db")

# List containing the different kinds of papers 
paper_supplies = [
    # Paper Types
    {"item_name": "A4 paper", "category": "paper", "unit_price": 0.05},
    {"item_name": "Letter-sized paper", "category": "paper", "unit_price": 0.06},
    {"item_name": "Cardstock", "category": "paper", "unit_price": 0.15},
    {"item_name": "Colored paper", "category": "paper", "unit_price": 0.10},
    {"item_name": "Glossy paper", "category": "paper", "unit_price": 0.20},
    {"item_name": "Matte paper", "category": "paper", "unit_price": 0.18},
    {"item_name": "Recycled paper", "category": "paper", "unit_price": 0.08},
    {"item_name": "Eco-friendly paper", "category": "paper", "unit_price": 0.12},
    {"item_name": "Poster paper", "category": "paper", "unit_price": 0.25},
    {"item_name": "Banner paper", "category": "paper", "unit_price": 0.30},
    {"item_name": "Kraft paper", "category": "paper", "unit_price": 0.10},
    {"item_name": "Construction paper", "category": "paper", "unit_price": 0.07},
    {"item_name": "Wrapping paper", "category": "paper", "unit_price": 0.15},
    {"item_name": "Glitter paper", "category": "paper", "unit_price": 0.22},
    {"item_name": "Decorative paper", "category": "paper", "unit_price": 0.18},
    {"item_name": "Letterhead paper", "category": "paper", "unit_price": 0.12},
    {"item_name": "Legal-size paper", "category": "paper", "unit_price": 0.08},
    {"item_name": "Crepe paper", "category": "paper", "unit_price": 0.05},
    {"item_name": "Photo paper", "category": "paper", "unit_price": 0.25},
    {"item_name": "Uncoated paper", "category": "paper", "unit_price": 0.06},
    {"item_name": "Butcher paper", "category": "paper", "unit_price": 0.10},
    {"item_name": "Heavyweight paper", "category": "paper", "unit_price": 0.20},
    {"item_name": "Standard copy paper", "category": "paper", "unit_price": 0.04},
    {"item_name": "Bright-colored paper", "category": "paper", "unit_price": 0.12},
    {"item_name": "Patterned paper", "category": "paper", "unit_price": 0.15},
    # Products
    {"item_name": "Paper plates", "category": "product", "unit_price": 0.10},
    {"item_name": "Paper cups", "category": "product", "unit_price": 0.08},
    {"item_name": "Paper napkins", "category": "product", "unit_price": 0.02},
    {"item_name": "Disposable cups", "category": "product", "unit_price": 0.10},
    {"item_name": "Table covers", "category": "product", "unit_price": 1.50},
    {"item_name": "Envelopes", "category": "product", "unit_price": 0.05},
    {"item_name": "Sticky notes", "category": "product", "unit_price": 0.03},
    {"item_name": "Notepads", "category": "product", "unit_price": 2.00},
    {"item_name": "Invitation cards", "category": "product", "unit_price": 0.50},
    {"item_name": "Flyers", "category": "product", "unit_price": 0.15},
    {"item_name": "Party streamers", "category": "product", "unit_price": 0.05},
    {"item_name": "Decorative adhesive tape (washi tape)", "category": "product", "unit_price": 0.20},
    {"item_name": "Paper party bags", "category": "product", "unit_price": 0.25},
    {"item_name": "Name tags with lanyards", "category": "product", "unit_price": 0.75},
    {"item_name": "Presentation folders", "category": "product", "unit_price": 0.50},
    # Large format
    {"item_name": "Large poster paper (24x36 inches)", "category": "large_format", "unit_price": 1.00},
    {"item_name": "Rolls of banner paper (36-inch width)", "category": "large_format", "unit_price": 2.50},
    # Specialty
    {"item_name": "100 lb cover stock", "category": "specialty", "unit_price": 0.50},
    {"item_name": "80 lb text paper", "category": "specialty", "unit_price": 0.40},
    {"item_name": "250 gsm cardstock", "category": "specialty", "unit_price": 0.30},
    {"item_name": "220 gsm poster paper", "category": "specialty", "unit_price": 0.35},
]

def generate_sample_inventory(paper_supplies: list, coverage: float = 0.4, seed: int = 137) -> pd.DataFrame:
    np.random.seed(seed)
    num_items = int(len(paper_supplies) * coverage)
    selected_indices = np.random.choice(range(len(paper_supplies)), size=num_items, replace=False)
    selected_items = [paper_supplies[i] for i in selected_indices]
    
    inventory = []
    for item in selected_items:
        inventory.append({
            "item_name": item["item_name"],
            "category": item["category"],
            "unit_price": item["unit_price"],
            "current_stock": np.random.randint(200, 800),
            "min_stock_level": np.random.randint(50, 150)
        })
    return pd.DataFrame(inventory)

def init_database(db_engine: Engine = db_engine, seed: int = 137) -> Engine:
    try:
        transactions_schema = pd.DataFrame({
            "id": [], "item_name": [], "transaction_type": [],
            "units": [], "price": [], "transaction_date": []
        })
        transactions_schema.to_sql("transactions", db_engine, if_exists="replace", index=False)
    
        initial_date = datetime(2025, 1, 1).isoformat()
        
        quote_requests_df = pd.read_csv("quote_requests.csv")
        quote_requests_df["id"] = range(1, len(quote_requests_df) + 1)
        quote_requests_df.to_sql("quote_requests", db_engine, if_exists="replace", index=False)
        
        quotes_df = pd.read_csv("quotes.csv")
        quotes_df["request_id"] = range(1, len(quotes_df) + 1)
        quotes_df["order_date"] = initial_date
        
        if "request_metadata" in quotes_df.columns:
            quotes_df["request_metadata"] = quotes_df["request_metadata"].apply(
                lambda x: ast.literal_eval(x) if isinstance(x, str) else x
            )
            quotes_df["job_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("job_type", ""))
            quotes_df["order_size"] = quotes_df["request_metadata"].apply(lambda x: x.get("order_size", ""))
            quotes_df["event_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("event_type", ""))
        
        quotes_df = quotes_df[["request_id", "total_amount", "quote_explanation", "order_date", "job_type", "order_size", "event_type"]]
        quotes_df.to_sql("quotes", db_engine, if_exists="replace", index=False)
        
        inventory_df = generate_sample_inventory(paper_supplies, seed=seed)
        initial_transactions = []
        
        initial_transactions.append({
            "item_name": None, "transaction_type": "sales",
            "units": None, "price": 50000.0, "transaction_date": initial_date
        })
        
        for _, item in inventory_df.iterrows():
            initial_transactions.append({
                "item_name": item["item_name"], "transaction_type": "stock_orders",
                "units": item["current_stock"],
                "price": item["current_stock"] * item["unit_price"],
                "transaction_date": initial_date
            })
        
        pd.DataFrame(initial_transactions).to_sql("transactions", db_engine, if_exists="append", index=False)
        inventory_df.to_sql("inventory", db_engine, if_exists="replace", index=False)
        return db_engine
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

def create_transaction(item_name: str, transaction_type: str, quantity: int, price: float, date: Union[str, datetime]) -> int:
    try:
        date_str = date.isoformat() if isinstance(date, datetime) else date
        if transaction_type not in {"stock_orders", "sales"}:
            raise ValueError("Transaction type must be 'stock_orders' or 'sales'")
        
        transaction = pd.DataFrame([{
            "item_name": item_name,
            "transaction_type": transaction_type,
            "units": quantity,
            "price": price,
            "transaction_date": date_str
        }])
        
        transaction.to_sql("transactions", db_engine, if_exists="append", index=False)
        result = pd.read_sql("SELECT last_insert_rowid() as id", db_engine)
        return int(result.iloc[0]["id"])
    except Exception as e:
        print(f"Error creating transaction: {e}")
        raise

def get_all_inventory(as_of_date: str) -> Dict[str, int]:
    query = """
        SELECT item_name,
            SUM(CASE
                WHEN transaction_type = 'stock_orders' THEN units
                WHEN transaction_type = 'sales' THEN -units
                ELSE 0
            END) as stock
        FROM transactions
        WHERE item_name IS NOT NULL AND transaction_date <= :as_of_date
        GROUP BY item_name
        HAVING stock > 0
    """
    result = pd.read_sql(query, db_engine, params={"as_of_date": as_of_date})
    return dict(zip(result["item_name"], result["stock"]))

def get_stock_level(item_name: str, as_of_date: Union[str, datetime]) -> pd.DataFrame:
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()
    
    stock_query = """
        SELECT item_name,
            COALESCE(SUM(CASE
                WHEN transaction_type = 'stock_orders' THEN units
                WHEN transaction_type = 'sales' THEN -units
                ELSE 0
            END), 0) AS current_stock
        FROM transactions
        WHERE item_name = :item_name AND transaction_date <= :as_of_date
    """
    return pd.read_sql(stock_query, db_engine, params={"item_name": item_name, "as_of_date": as_of_date})

def get_supplier_delivery_date(input_date_str: str, quantity: int) -> str:
    try:
        input_date_dt = datetime.fromisoformat(input_date_str.split("T")[0])
    except (ValueError, TypeError):
        input_date_dt = datetime.now()
    
    if quantity <= 10:
        days = 0
    elif quantity <= 100:
        days = 1
    elif quantity <= 1000:
        days = 4
    else:
        days = 7
    
    delivery_date_dt = input_date_dt + timedelta(days=days)
    return delivery_date_dt.strftime("%Y-%m-%d")

def get_cash_balance(as_of_date: Union[str, datetime]) -> float:
    try:
        if isinstance(as_of_date, datetime):
            as_of_date = as_of_date.isoformat()
        
        transactions = pd.read_sql(
            "SELECT * FROM transactions WHERE transaction_date <= :as_of_date",
            db_engine, params={"as_of_date": as_of_date}
        )
        
        if not transactions.empty:
            total_sales = transactions.loc[transactions["transaction_type"] == "sales", "price"].sum()
            total_purchases = transactions.loc[transactions["transaction_type"] == "stock_orders", "price"].sum()
            return float(total_sales - total_purchases)
        return 0.0
    except Exception as e:
        print(f"Error getting cash balance: {e}")
        return 0.0

def generate_financial_report(as_of_date: Union[str, datetime]) -> Dict:
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()
    
    cash = get_cash_balance(as_of_date)
    inventory_df = pd.read_sql("SELECT * FROM inventory", db_engine)
    inventory_value = 0.0
    inventory_summary = []
    
    for _, item in inventory_df.iterrows():
        stock_info = get_stock_level(item["item_name"], as_of_date)
        stock = stock_info["current_stock"].iloc[0]
        item_value = stock * item["unit_price"]
        inventory_value += item_value
        
        inventory_summary.append({
            "item_name": item["item_name"], "stock": stock,
            "unit_price": item["unit_price"], "value": item_value
        })
    
    top_sales_query = """
        SELECT item_name, SUM(units) as total_units, SUM(price) as total_revenue
        FROM transactions
        WHERE transaction_type = 'sales' AND transaction_date <= :date
        GROUP BY item_name
        ORDER BY total_revenue DESC
        LIMIT 5
    """
    top_sales = pd.read_sql(top_sales_query, db_engine, params={"date": as_of_date})
    top_selling_products = top_sales.to_dict(orient="records")
    
    return {
        "as_of_date": as_of_date, "cash_balance": cash, "inventory_value": inventory_value,
        "total_assets": cash + inventory_value,
        "inventory_summary": inventory_summary,
        "top_selling_products": top_selling_products
    }

def search_quote_history(search_terms: List[str], limit: int = 5) -> List[Dict]:
    conditions = []
    params = {}
    
    for i, term in enumerate(search_terms):
        param_name = f"term_{i}"
        conditions.append(
            f"(LOWER(qr.response) LIKE :{param_name} OR "
            f"LOWER(q.quote_explanation) LIKE :{param_name})"
        )
        params[param_name] = f"%{term.lower()}%"
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    query = f"""
        SELECT qr.response AS original_request, q.total_amount, q.quote_explanation,
            q.job_type, q.order_size, q.event_type, q.order_date
        FROM quotes q
        JOIN quote_requests qr ON q.request_id = qr.id
        WHERE {where_clause}
        ORDER BY q.order_date DESC
        LIMIT {limit}
    """
    
    with db_engine.connect() as conn:
        result = conn.execute(text(query), params)
        return [dict(row._mapping) for row in result]

# AGENT TOOLS
@tool
def check_inventory_availability(items_json: str, check_date: str) -> str:
    """Check inventory availability for requested items.
    
    Args:
        items_json: JSON string like '[{"item_name":"A4 paper","quantity":500}]'
        check_date: Date in YYYY-MM-DD format
    
    Returns:
        Availability status for each item
    """
    try:
        items = json.loads(items_json)
        results = []
        
        for item in items:
            name = item["item_name"]
            qty = item["quantity"]
            
            stock_df = get_stock_level(name, check_date)
            if stock_df.empty or len(stock_df) == 0:
                results.append(f"X {name}: NOT IN INVENTORY")
            else:
                current_stock = int(stock_df.iloc[0]["current_stock"])
                if current_stock >= qty:
                    results.append(f"OK {name}: {current_stock} available (requested {qty})")
                else:
                    results.append(f"WARNING {name}: Only {current_stock} available (requested {qty}, short {qty-current_stock})")
        
        return "\n".join(results)
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def search_past_quotes(keywords: str) -> str:
    """Search historical quotes for similar orders.
    
    Args:
        keywords: Comma-separated keywords (e.g. "wedding,glossy,cards")
    
    Returns:
        Summary of past quotes
    """
    try:
        terms = [k.strip() for k in keywords.split(",")]
        quotes = search_quote_history(terms, 5)
        
        if not quotes:
            return "No similar quotes found."
        
        output = []
        for i, q in enumerate(quotes, 1):
            output.append(f"\n=== Quote {i} ===")
            output.append(f"Event: {q.get('event_type','N/A')}, Size: {q.get('order_size','N/A')}")
            output.append(f"Amount: ${q['total_amount']:.2f}")
            output.append(f"Details: {q['quote_explanation'][:120]}...")
        
        return "\n".join(output)
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def create_quote(items_json: str, quote_date: str) -> str:
    """Generate a price quote with bulk discounts.
    
    Args:
        items_json: JSON string like '[{"item_name":"A4 paper","quantity":500}]'
        quote_date: Date in YYYY-MM-DD format
    
    Returns:
        Detailed quote with pricing
    """
    try:
        items = json.loads(items_json)
        DISCOUNTS = [(1000, 0.15, "15%"), (500, 0.10, "10%"), (100, 0.05, "5%")]
        price_map = {i["item_name"]: i["unit_price"] for i in paper_supplies}
        
        lines = []
        total = 0.0
        
        for item in items:
            name = item["item_name"]
            qty = item["quantity"]
            
            if name not in price_map:
                lines.append(f"  X {name}: NOT IN CATALOG")
                continue
            
            base = price_map[name]
            disc = 0.0
            disc_label = ""
            
            for min_qty, rate, label in DISCOUNTS:
                if qty >= min_qty:
                    disc = rate
                    disc_label = f" ({label} bulk discount)"
                    break
            
            final = base * (1 - disc)
            line_total = final * qty
            total += line_total
            
            lines.append(f"  • {name}: {qty} units @ ${base:.4f}{disc_label}")
            if disc > 0:
                lines.append(f"    Final price: ${final:.4f} each")
            lines.append(f"    Subtotal: ${line_total:.2f}")
        
        lines.append(f"\nTOTAL: ${total:.2f}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def process_customer_sale(items_json: str, sale_date: str) -> str:
    """Process a sale and record transactions.
    
    Args:
        items_json: JSON string like '[{"item_name":"A4 paper","quantity":500}]'
        sale_date: Date in YYYY-MM-DD format
    
    Returns:
        Sale confirmation
    """
    try:
        items = json.loads(items_json)
        
        for item in items:
            stock_df = get_stock_level(item["item_name"], sale_date)
            if stock_df.empty:
                return f"X SALE FAILED: {item['item_name']} not in inventory"
            
            stock = int(stock_df.iloc[0]["current_stock"])
            if stock < item["quantity"]:
                return f"X SALE FAILED: Insufficient {item['item_name']} (have {stock}, need {item['quantity']})"
        
        price_map = {i["item_name"]: i["unit_price"] for i in paper_supplies}
        total = 0.0
        
        for item in items:
            name = item["item_name"]
            qty = item["quantity"]
            base = price_map[name]
            
            disc = 0.15 if qty >= 1000 else 0.10 if qty >= 500 else 0.05 if qty >= 100 else 0.0
            final = base * (1 - disc)
            amount = final * qty
            total += amount
            
            create_transaction(name, "sales", qty, amount, sale_date)
        
        return f"OK SALE PROCESSED! Total revenue: ${total:.2f}"
    except Exception as e:
        return f"X Error: {str(e)}"

@tool
def restock_from_supplier(item_name: str, quantity: int, order_date: str) -> str:
    """Order stock from supplier (costs 60% of retail).
    
    Args:
        item_name: Item to order
        quantity: Quantity to order
        order_date: Date in YYYY-MM-DD format
    
    Returns:
        Order confirmation
    """
    try:
        price_map = {i["item_name"]: i["unit_price"] for i in paper_supplies}
        
        if item_name not in price_map:
            return f"X ORDER FAILED: {item_name} not in catalog"
        
        supplier_cost = price_map[item_name] * 0.6 * quantity
        cash = get_cash_balance(order_date)
        
        if cash < supplier_cost:
            return f"X ORDER FAILED: Insufficient funds (need ${supplier_cost:.2f}, have ${cash:.2f})"
        
        delivery = get_supplier_delivery_date(order_date, quantity)
        create_transaction(item_name, "stock_orders", quantity, supplier_cost, order_date)
        
        return f"OK RESTOCKED! {item_name} x{quantity}, Cost: ${supplier_cost:.2f}, Delivery: {delivery}"
    except Exception as e:
        return f"X Error: {str(e)}"

@tool
def check_cash(date: str) -> str:
    """Get current cash balance.
    
    Args:
        date: Date in YYYY-MM-DD format
    
    Returns:
        Cash balance
    """
    try:
        balance = get_cash_balance(date)
        return f"Cash balance: ${balance:.2f}"
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def get_full_inventory_report(date: str) -> str:
    """Get complete inventory snapshot showing all items in stock.
    
    Args:
        date: Date in YYYY-MM-DD format
    
    Returns:
        Formatted inventory report
    """
    try:
        inventory = get_all_inventory(date)
        
        if not inventory:
            return "No items currently in stock."
        
        lines = ["CURRENT INVENTORY:"]
        total_items = 0
        
        for item_name, stock in sorted(inventory.items()):
            lines.append(f"  • {item_name}: {stock} units")
            total_items += stock
        
        lines.append(f"\nTotal items in stock: {total_items} units across {len(inventory)} product types")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def get_financial_summary(date: str) -> str:
    """Generate comprehensive financial report including cash, inventory value, and assets.
    
    Args:
        date: Date in YYYY-MM-DD format
    
    Returns:
        Formatted financial report
    """
    try:
        report = generate_financial_report(date)
        
        lines = ["FINANCIAL SUMMARY:"]
        lines.append(f"  Date: {report['as_of_date']}")
        lines.append(f"  Cash Balance: ${report['cash_balance']:.2f}")
        lines.append(f"  Inventory Value: ${report['inventory_value']:.2f}")
        lines.append(f"  Total Assets: ${report['total_assets']:.2f}")
        
        if report['top_selling_products']:
            lines.append(f"\nTop Selling Products:")
            for i, product in enumerate(report['top_selling_products'][:3], 1):
                if product.get('item_name'):
                    lines.append(f"  {i}. {product['item_name']}: ${product.get('total_revenue', 0):.2f} revenue")
        
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"

# SETUP
dotenv.load_dotenv(dotenv_path=".env")
api_key = os.getenv("OPENAI_API_KEY")

model = OpenAIServerModel(
    model_id="gpt-4o-mini",
    api_key="voc-141343078168865450535868fbb7344683e6.02198483",
    api_base="https://openai.vocareum.com/v1"
)

########################
# MULTI-AGENT SYSTEM
########################

# Worker Agent 1: Inventory Agent
# Responsible for stock checking, inventory reporting, and financial status
inventory_agent = ToolCallingAgent(
    tools=[
        check_inventory_availability,
        get_full_inventory_report,
        check_cash,
        get_financial_summary
    ],
    model=model,
    max_steps=10
)

# Worker Agent 2: Quotation Agent
# Responsible for pricing, quote generation, and historical analysis
quotation_agent = ToolCallingAgent(
    tools=[
        search_past_quotes,
        create_quote
    ],
    model=model,
    max_steps=10
)

# Worker Agent 3: Sales-Fulfillment Agent
# Responsible for order processing and supplier restocking
sales_agent = ToolCallingAgent(
    tools=[
        process_customer_sale,
        restock_from_supplier
    ],
    model=model,
    max_steps=10
)

########################
# ORCHESTRATOR
########################

def orchestrate_request(request_text: str, request_date: str) -> str:
    """
    Orchestrator that coordinates multiple agents to handle customer requests.
    
    This function analyzes the customer request and delegates tasks to appropriate
    worker agents (Inventory, Quotation, Sales) in the correct sequence.
    
    Args:
        request_text: Customer's request
        request_date: Date of the request (YYYY-MM-DD)
    
    Returns:
        Final customer-facing response
    """
    try:
        # Determine if this is a quote request or an order
        is_order = any(keyword in request_text.lower() for keyword in ['order', 'buy', 'purchase', 'place an order'])
        
        # Extract items from request (simplified - could be enhanced with better parsing)
        # For now, we'll let the agents handle the extraction
        
        responses = []
        
        # Step 1: Check inventory availability (Inventory Agent)
        inventory_prompt = f"""Today is {request_date}.

Customer request: {request_text}

Task: Check if we have the requested items in stock.
- Extract item names and quantities from the request
- Map informal names to exact catalog names (e.g., "glossy paper" to "Glossy paper")
- Use check_inventory_availability to verify stock levels
- Report availability status

Available items include: A4 paper, Cardstock, Colored paper, Glossy paper, Matte paper, Poster paper, 
Construction paper, Photo paper, Paper plates, Paper cups, Paper napkins, Envelopes, Sticky notes, 
Notepads, Invitation cards, Flyers, Party streamers, and more."""

        inventory_response = inventory_agent.run(inventory_prompt)
        responses.append(f"INVENTORY CHECK:\n{inventory_response}")
        
        # Step 2: Generate quote (Quotation Agent)
        quote_prompt = f"""Today is {request_date}.

Customer request: {request_text}
Inventory status: {inventory_response}

Task: Generate a professional price quote.
- Search for similar past quotes for pricing guidance
- Calculate prices with bulk discounts (15% for 1000+, 10% for 500+, 5% for 100+)
- Provide detailed line-item breakdown
- Show transparent pricing

Use create_quote to generate the final quote."""

        quote_response = quotation_agent.run(quote_prompt)
        responses.append(f"QUOTE:\n{quote_response}")
        
        # Step 3: If it's an order, process the sale (Sales Agent)
        if is_order:
            sales_prompt = f"""Today is {request_date}.

Customer request: {request_text}
Inventory status: {inventory_response}
Quote: {quote_response}

Task: Process the customer order.
- Use process_customer_sale to record the transaction
- After sale, check if restocking is needed
- If inventory is low and funds available, use restock_from_supplier

Provide confirmation of the sale and any restock actions."""

            sales_response = sales_agent.run(sales_prompt)
            responses.append(f"ORDER PROCESSING:\n{sales_response}")
        
        # Synthesize final customer response
        if is_order:
            final_response = f"""Thank you for your order!

{quote_response}

{sales_response}

Your order has been processed. We appreciate your business!"""
        else:
            final_response = f"""Thank you for your inquiry!

{quote_response}

All quoted items are based on current availability. Please let us know if you'd like to proceed with this order."""
        
        return final_response
        
    except Exception as e:
        print(f"Orchestrator error: {str(e)}")
        return f"We apologize, but we encountered an issue processing your request. Please contact our support team. (Error: {str(e)[:100]})"

def run_test_scenarios():
    print("=" * 60)
    print("INITIALIZING DATABASE...")
    print("=" * 60)
    init_database(db_engine=db_engine)
    
    try:
        df = pd.read_csv("quote_requests_sample.csv")
        df["request_date"] = pd.to_datetime(df["request_date"], format="%m/%d/%y", errors="coerce")
        df = df.dropna(subset=["request_date"]).sort_values("request_date")
    except Exception as e:
        print(f"FATAL: Error loading test data: {e}")
        return None
    
    initial_date = df["request_date"].min().strftime("%Y-%m-%d")
    report = generate_financial_report(initial_date)
    current_cash = report["cash_balance"]
    current_inventory = report["inventory_value"]
    
    print(f"\nInitial Cash: ${current_cash:.2f}")
    print(f"Initial Inventory Value: ${current_inventory:.2f}\n")
    
    results = []
    
    for idx, row in df.iterrows():
        request_date = row["request_date"].strftime("%Y-%m-%d")
        
        print("\n" + "="*60)
        print(f"REQUEST {idx+1}")
        print("="*60)
        print(f"Job: {row['job']} | Event: {row['event']}")
        print(f"Date: {request_date}")
        print(f"Cash: ${current_cash:.2f} | Inventory: ${current_inventory:.2f}")
        print(f"\nRequest: {row['request'][:100]}...")
        print("-"*60)
        
        request_with_date = f"{row['request']} (Date: {request_date})"
        response = orchestrate_request(request_with_date, request_date)
        
        report = generate_financial_report(request_date)
        current_cash = report["cash_balance"]
        current_inventory = report["inventory_value"]
        
        print(f"\nResponse: {response[:200]}...")
        print(f"\nUpdated Cash: ${current_cash:.2f}")
        print(f"Updated Inventory: ${current_inventory:.2f}")
        
        results.append({
            "request_id": idx + 1,
            "request_date": request_date,
            "cash_balance": current_cash,
            "inventory_value": current_inventory,
            "response": response
        })
        
        time.sleep(1)
    
    final_date = df["request_date"].max().strftime("%Y-%m-%d")
    final_report = generate_financial_report(final_date)
    
    print("\n" + "="*60)
    print("FINAL FINANCIAL REPORT")
    print("="*60)
    print(f"Final Cash: ${final_report['cash_balance']:.2f}")
    print(f"Final Inventory: ${final_report['inventory_value']:.2f}")
    print(f"Total Assets: ${final_report['total_assets']:.2f}")
    print("="*60)
    
    pd.DataFrame(results).to_csv("test_results.csv", index=False)
    print("\nResults saved to test_results.csv")
    
    return results

if __name__ == "__main__":
    results = run_test_scenarios()
