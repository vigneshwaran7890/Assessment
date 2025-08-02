import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import sqlite3
import logging
import re
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Set up logging
logging.basicConfig(filename='wms.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

class SKUMapper:
    def __init__(self, conn):
        self.conn = conn
        self.msku_mappings = {}
        self.predefined_mappings = {
            'MUSIC_BOX': [
                'MTYGAUZJFZAAZXYJ', 'MTYGFYU2AXY4VUYQ', 'MTYGYX7YB7DJ5HSF',
                'MTYGF8CKEZVGPZGX', 'MTYGYZGGV5NGQRXG', 'MBXGPK2WHAWYW4UF',
                'MTYGADJZHJYSDTXB', 'MTYGACBNGZPTDBGZ', 'MBXF894GJXNQ79DN',
                'MTYGYZJRGAKY3AEJ', 'OTYGU29RCH3FZZP8', 'OTYGU25AZFNXZRXX'
            ],
            'PLUSH_TOY': [
                'STFH8CZHGFBB8RHP', 'STFH6QTVHNR3JSYZ', 'STFH76G8G2ZAGFVZ',
                'STFH6QQNDEQTBMCK', 'STFH6QTDZDU3JMTG', 'STFH63ZFB9NC9NZQ',
                'STFH74ECSV8DWJHF', 'STFH6FDUWS2FRN4T', 'STFH6GXUYCBZGQB5',
                'STFH8CZKNCEHTG2A', 'STFH6GYMKWBPBFQ5', 'STFH6MNQVEXTFE7S',
                'STFG4PZP2YENG4NN', 'STFH6GYEKCGYZQ5M'
            ],
            'SUNGLASSES': [
                'SGLG5E7ZZWHFNTFH', 'SGLGQSDZH7TP4CTF', 'SGLGQQ9QN2M6TFH7',
                'SGLGFYUGHZHXSZWD', 'SGLGQSHAWZZEJPHW'
            ],
            'TOY_WEAPON': [
                'TWPH6ZHTQ3STVASV', 'STFH6QPFQHH9FHZH', 'STFH6QQNDEQTBMCK',
                'OTYGUM6DFKP8WTNW', 'OTYGUGHAGZNTZTCZ'
            ],
            'MUSIC_INSTRUMENT': [
                'PNLGT3YH6CHBRXRS', 'PNLGT3YMUSHSEPXA'
            ],
            'WATCH': ['WATG5ATMAD7U2KGS']
        }
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS msku_mappings (
                sku TEXT PRIMARY KEY,
                msku TEXT,
                marketplace TEXT,
                last_updated TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales_data (
                order_id TEXT PRIMARY KEY,
                sku TEXT,
                msku TEXT,
                quantity INTEGER,
                price REAL,
                date TIMESTAMP,
                marketplace TEXT,
                state TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                sku TEXT PRIMARY KEY,
                msku TEXT,
                product_name TEXT,
                stock_quantity INTEGER
            )
        ''')
        self.conn.commit()
        # Populate predefined mappings
        for msku, skus in self.predefined_mappings.items():
            for sku in skus:
                cursor.execute('''
                    INSERT OR IGNORE INTO msku_mappings (sku, msku, marketplace, last_updated)
                    VALUES (?, ?, ?, ?)
                ''', (sku, msku, 'default', datetime.now()))
        self.conn.commit()

    def load_mappings(self, mapping_file):
        try:
            df = pd.read_csv(mapping_file)
            cursor = self.conn.cursor()
            for _, row in df.iterrows():
                sku = row['SKU']
                msku = row['MSKU']
                marketplace = row.get('marketplace', 'default')
                cursor.execute('''
                    INSERT OR REPLACE INTO msku_mappings (sku, msku, marketplace, last_updated)
                    VALUES (?, ?, ?, ?)
                ''', (sku, msku, marketplace, datetime.now()))
                self.msku_mappings[sku] = {'msku': msku, 'marketplace': marketplace}
            self.conn.commit()
            logging.info(f"Loaded {len(df)} SKU mappings from file")
        except Exception as e:
            logging.error(f"Error loading mappings: {str(e)}")
            raise

    def validate_sku_format(self, sku):
        # Basic SKU format validation (alphanumeric with optional hyphens)
        pattern = r'^[A-Za-z0-9\-]+$'
        return bool(re.match(pattern, sku))

    def map_sku(self, sku):
        if not self.validate_sku_format(sku):
            logging.warning(f"Invalid SKU format: {sku}")
            return None
        cursor = self.conn.cursor()
        cursor.execute('SELECT msku FROM msku_mappings WHERE sku = ?', (sku,))
        result = cursor.fetchone()
        return result[0] if result else 'UNKNOWN'

    def save_mapping(self, sku, msku, marketplace='default'):
        if not self.validate_sku_format(sku):
            logging.warning(f"Invalid SKU format: {sku}")
            raise ValueError("Invalid SKU format")
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO msku_mappings (sku, msku, marketplace, last_updated)
            VALUES (?, ?, ?, ?)
        ''', (sku, msku, marketplace, datetime.now()))
        self.conn.commit()
        self.msku_mappings[sku] = {'msku': msku, 'marketplace': marketplace}
        logging.info(f"Saved mapping: {sku} -> {msku}")

class WMSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Warehouse Management System")
        self.root.geometry("1200x800")
        self.conn = sqlite3.connect('wms_database.db')
        self.sku_mapper = SKUMapper(self.conn)
        self.sales_data = None
        self.setup_gui()

    def setup_gui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # File upload section
        ttk.Button(main_frame, text="Load Mapping File", command=self.load_mapping_file).grid(row=0, column=0, pady=5)
        ttk.Button(main_frame, text="Load Sales Data", command=self.load_sales_data).grid(row=0, column=1, pady=5)
        ttk.Button(main_frame, text="Generate Sales Report", command=self.generate_sales_report).grid(row=0, column=2, pady=5)
        ttk.Button(main_frame, text="View Inventory", command=self.view_inventory).grid(row=0, column=3, pady=5)
        
        # SKU Mapping section
        ttk.Label(main_frame, text="SKU:").grid(row=1, column=0, pady=5)
        self.sku_entry = ttk.Entry(main_frame)
        self.sku_entry.grid(row=1, column=1, pady=5)
        
        ttk.Label(main_frame, text="MSKU:").grid(row=2, column=0, pady=5)
        self.msku_entry = ttk.Entry(main_frame)
        self.msku_entry.grid(row=2, column=1, pady=5)
        
        ttk.Button(main_frame, text="Map SKU", command=self.map_sku).grid(row=3, column=0, columnspan=2, pady=5)
        
        # Treeview for data display
        self.tree = ttk.Treeview(main_frame, columns=('Order ID', 'SKU', 'MSKU', 'Product', 'Quantity', 'Price', 'Date', 'State'), show='headings')
        self.tree.heading('Order ID', text='Order ID')
        self.tree.heading('SKU', text='SKU')
        self.tree.heading('MSKU', text='MSKU')
        self.tree.heading('Product', text='Product Name')
        self.tree.heading('Quantity', text='Quantity')
        self.tree.heading('Price', text='Price (INR)')
        self.tree.heading('Date', text='Order Date')
        self.tree.heading('State', text='State')
        self.tree.grid(row=4, column=0, columnspan=4, pady=10, sticky=(tk.W, tk.E))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.grid(row=4, column=4, sticky=(tk.N, tk.S))
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Plot frame
        self.plot_frame = ttk.Frame(main_frame)
        self.plot_frame.grid(row=5, column=0, columnspan=4, pady=10)
        
        # SQL Query section
        ttk.Label(main_frame, text="SQL Query:").grid(row=6, column=0, pady=5)
        self.query_entry = ttk.Entry(main_frame, width=50)
        self.query_entry.grid(row=6, column=1, columnspan=3, pady=5)
        ttk.Button(main_frame, text="Execute Query", command=self.execute_query).grid(row=7, column=0, columnspan=4, pady=5)

    def load_mapping_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if file_path:
            try:
                self.sku_mapper.load_mappings(file_path)
                messagebox.showinfo("Success", "Mapping file loaded successfully")
            except Exception as e:
                logging.error(f"Failed to load mapping file: {str(e)}")
                messagebox.showerror("Error", f"Failed to load mapping file: {str(e)}")

    def load_sales_data(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if file_path:
            try:
                self.sales_data = pd.read_csv(file_path)
                self.process_sales_data()
                messagebox.showinfo("Success", "Sales data loaded successfully")
            except Exception as e:
                logging.error(f"Failed to load sales data: {str(e)}")
                messagebox.showerror("Error", f"Failed to load sales data: {str(e)}")

    def process_sales_data(self):
        cursor = self.conn.cursor()
        for _, row in self.sales_data.iterrows():
            sku = row['SKU']
            msku = self.sku_mapper.map_sku(sku)
            product_name = row['Product']
            quantity = int(row['Quantity'])
            price = float(row['Invoice Amount'])
            order_id = row['Order Id']
            date = row['Ordered On']
            state = row['State']
            
            cursor.execute('''
                INSERT OR REPLACE INTO sales_data (order_id, sku, msku, quantity, price, date, marketplace, state)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (order_id, sku, msku, quantity, price, date, 'default', state))
            
            # Update inventory (default stock quantity for demo)
            cursor.execute('''
                INSERT OR REPLACE INTO inventory (sku, msku, product_name, stock_quantity)
                VALUES (?, ?, ?, ?)
            ''', (sku, msku, product_name, 100))  # Default stock for demo
        self.conn.commit()
        self.display_sales_data()

    def map_sku(self):
        sku = self.sku_entry.get()
        msku = self.msku_entry.get()
        if sku and msku:
            try:
                self.sku_mapper.save_mapping(sku, msku)
                messagebox.showinfo("Success", f"SKU {sku} mapped to MSKU {msku}")
                self.display_sales_data()
            except Exception as e:
                logging.error(f"Failed to map SKU: {str(e)}")
                messagebox.showerror("Error", f"Failed to map SKU: {str(e)}")
        else:
            messagebox.showerror("Error", "Please enter both SKU and MSKU")

    def display_sales_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        cursor = self.conn.cursor()
        cursor.execute('SELECT order_id, sku, msku, product_name, quantity, price, date, state FROM sales_data')
        for row in cursor.fetchall():
            self.tree.insert('', 'end', values=row)

    def generate_sales_report(self):
        if self.sales_data is None:
            messagebox.showwarning("Warning", "Please load sales data first")
            return
        
        # Clear previous plot
        for widget in self.plot_frame.winfo_children():
            widget.destroy()
        
        # Sales by MSKU
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        # Process data
        self.sales_data['MSKU'] = self.sales_data['SKU'].apply(self.sku_mapper.map_sku)
        sales_by_msku = self.sales_data.groupby('MSKU').agg({'Quantity': 'sum', 'Invoice Amount': 'sum'}).reset_index()
        
        # Bar plot for quantity
        ax1.bar(sales_by_msku['MSKU'], sales_by_msku['Quantity'], color='#1f77b4')
        ax1.set_title('Sales Quantity by MSKU')
        ax1.set_xlabel('MSKU')
        ax1.set_ylabel('Quantity')
        ax1.tick_params(axis='x', rotation=45)
        
        # Bar plot for revenue
        ax2.bar(sales_by_msku['MSKU'], sales_by_msku['Invoice Amount'], color='#ff7f0e')
        ax2.set_title('Revenue by MSKU')
        ax2.set_xlabel('MSKU')
        ax2.set_ylabel('Revenue (INR)')
        ax2.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        
        # Embed plot in tkinter
        canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
        canvas.draw()
        canvas.get_tk_widget().pack()

    def view_inventory(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        self.tree.configure(columns=('SKU', 'MSKU', 'Product', 'Stock Quantity'))
        self.tree.heading('SKU', text='SKU')
        self.tree.heading('MSKU', text='MSKU')
        self.tree.heading('Product', text='Product Name')
        self.tree.heading('Stock Quantity', text='Stock Quantity')
        
        cursor = self.conn.cursor()
        cursor.execute('SELECT sku, msku, product_name, stock_quantity FROM inventory')
        for row in cursor.fetchall():
            self.tree.insert('', 'end', values=row)

    def execute_query(self):
        query = self.query_entry.get()
        try:
            df = pd.read_sql_query(query, self.conn)
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Update treeview columns based on query results
            self.tree.configure(columns=tuple(df.columns), show='headings')
            for col in df.columns:
                self.tree.heading(col, text=col)
            
            for _, row in df.iterrows():
                self.tree.insert('', 'end', values=tuple(row))
            
            # Update visualization if applicable
            if 'SELECT' in query.upper() and len(df.columns) >= 2:
                for widget in self.plot_frame.winfo_children():
                    widget.destroy()
                
                fig, ax = plt.subplots(figsize=(8, 4))
                if df.select_dtypes(include=['int64', 'float64']).columns.size > 0:
                    numeric_col = df.select_dtypes(include=['int64', 'float64']).columns[0]
                    df.groupby(df.columns[0])[numeric_col].sum().plot(kind='bar', ax=ax, color='#2ca02c')
                    ax.set_title('Query Results')
                    ax.set_xlabel(df.columns[0])
                    ax.set_ylabel(numeric_col)
                    ax.tick_params(axis='x', rotation=45)
                    canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
                    canvas.draw()
                    canvas.get_tk_widget().pack()
            
            messagebox.showinfo("Query Result", f"Query executed successfully. Rows returned: {len(df)}")
        except Exception as e:
            logging.error(f"Query failed: {str(e)}")
            messagebox.showerror("Error", f"Query failed: {str(e)}")

    def __del__(self):
        self.conn.close()

if __name__ == "__main__":
    root = tk.Tk()
    app = WMSApp(root)
    root.mainloop()