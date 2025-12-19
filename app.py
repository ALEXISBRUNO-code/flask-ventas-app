from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, Usuario, Producto, Cliente, Venta, DetalleVenta
from config import Config
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func, desc
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from openpyxl import Workbook

app = Flask(__name__)
app.config.from_object(Config)

# Inicializar extensiones
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor inicia sesión para acceder a esta página'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Crear tablas y datos iniciales
with app.app_context():
    db.create_all()
    
    # Crear usuario admin si no existe
    if not Usuario.query.filter_by(username='admin').first():
        admin = Usuario(
            username='admin',
            nombre='Administrador',
            rol='admin'
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("Usuario admin creado - Username: admin, Password: admin123")
    
    # Crear productos iniciales si no existen
    if Producto.query.count() == 0:
        productos_iniciales = [
            Producto(nombre='iPhone 15 Pro', categoria='Smartphones', precio=4999.00, stock=15, stock_minimo=5),
            Producto(nombre='Samsung Galaxy S24', categoria='Smartphones', precio=3999.00, stock=20, stock_minimo=5),
            Producto(nombre='MacBook Air M3', categoria='Laptops', precio=5999.00, stock=10, stock_minimo=3),
            Producto(nombre='Dell XPS 15', categoria='Laptops', precio=4500.00, stock=8, stock_minimo=3),
            Producto(nombre='iPad Pro 12.9', categoria='Tablets', precio=4299.00, stock=12, stock_minimo=4),
            Producto(nombre='AirPods Pro 2', categoria='Accesorios', precio=899.00, stock=30, stock_minimo=10),
            Producto(nombre='Apple Watch Series 9', categoria='Smartwatches', precio=1899.00, stock=18, stock_minimo=5),
            Producto(nombre='Sony WH-1000XM5', categoria='Accesorios', precio=1499.00, stock=25, stock_minimo=8),
            Producto(nombre='Logitech MX Master 3S', categoria='Accesorios', precio=349.00, stock=40, stock_minimo=15),
            Producto(nombre='Samsung Monitor 27" 4K', categoria='Monitores', precio=1299.00, stock=15, stock_minimo=5)
        ]
        db.session.bulk_save_objects(productos_iniciales)
        db.session.commit()
        print("Productos iniciales creados")

# ==================== RUTAS DE AUTENTICACIÓN ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        usuario = Usuario.query.filter_by(username=username).first()
        
        if usuario and usuario.check_password(password):
            if not usuario.activo:
                flash('Tu cuenta está desactivada. Contacta al administrador.', 'error')
                return redirect(url_for('login'))
            
            login_user(usuario)
            flash(f'¡Bienvenido {usuario.nombre}!', 'success')
            
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión correctamente', 'info')
    return redirect(url_for('login'))

# ==================== RUTAS PRINCIPALES ====================

@app.route('/')
@login_required
def index():
    # Estadísticas rápidas
    total_productos = Producto.query.filter_by(activo=True).count()
    total_clientes = Cliente.query.filter_by(activo=True).count()
    ventas_hoy = Venta.query.filter(
        func.date(Venta.fecha) == datetime.utcnow().date()
    ).count()
    productos_stock_bajo = Producto.query.filter(
        Producto.stock <= Producto.stock_minimo,
        Producto.activo == True
    ).count()
    
    return render_template('index.html',
                         total_productos=total_productos,
                         total_clientes=total_clientes,
                         ventas_hoy=ventas_hoy,
                         productos_stock_bajo=productos_stock_bajo)

# ==================== RUTAS DE PRODUCTOS ====================

@app.route('/inventario')
@login_required
def inventario():
    busqueda = request.args.get('buscar', '')
    categoria = request.args.get('categoria', '')
    
    query = Producto.query.filter_by(activo=True)
    
    if busqueda:
        query = query.filter(Producto.nombre.ilike(f'%{busqueda}%'))
    
    if categoria:
        query = query.filter_by(categoria=categoria)
    
    productos = query.all()
    categorias = db.session.query(Producto.categoria).distinct().all()
    categorias = [c[0] for c in categorias]
    
    return render_template('inventario.html', productos=productos, categorias=categorias)

@app.route('/api/productos')
@login_required
def api_productos():
    productos = Producto.query.filter_by(activo=True).all()
    return jsonify([{
        'id': p.id,
        'nombre': p.nombre,
        'categoria': p.categoria,
        'precio': p.precio,
        'stock': p.stock,
        'stock_bajo': p.stock_bajo
    } for p in productos])

# ==================== RUTAS DE CLIENTES ====================

@app.route('/clientes')
@login_required
def clientes():
    busqueda = request.args.get('buscar', '')
    
    query = Cliente.query.filter_by(activo=True)
    
    if busqueda:
        query = query.filter(
            db.or_(
                Cliente.nombre.ilike(f'%{busqueda}%'),
                Cliente.documento.ilike(f'%{busqueda}%')
            )
        )
    
    clientes_lista = query.all()
    return render_template('clientes.html', clientes=clientes_lista)

@app.route('/clientes/nuevo', methods=['POST'])
@login_required
def nuevo_cliente():
    try:
        cliente = Cliente(
            nombre=request.form.get('nombre'),
            documento=request.form.get('documento'),
            tipo_documento=request.form.get('tipo_documento', 'DNI'),
            telefono=request.form.get('telefono'),
            email=request.form.get('email'),
            direccion=request.form.get('direccion')
        )
        
        db.session.add(cliente)
        db.session.commit()
        
        flash('Cliente registrado exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al registrar cliente: {str(e)}', 'error')
    
    return redirect(url_for('clientes'))

@app.route('/api/clientes')
@login_required
def api_clientes():
    clientes_lista = Cliente.query.filter_by(activo=True).all()
    return jsonify([{
        'id': c.id,
        'nombre': c.nombre,
        'documento': c.documento,
        'tipo_documento': c.tipo_documento
    } for c in clientes_lista])

# ==================== RUTAS DE VENTAS ====================

@app.route('/ventas')
@login_required
def ventas():
    productos = Producto.query.filter_by(activo=True).all()
    clientes_lista = Cliente.query.filter_by(activo=True).all()
    return render_template('ventas.html', productos=productos, clientes=clientes_lista)

@app.route('/ventas/registrar', methods=['POST'])
@login_required
def registrar_venta():
    try:
        data = request.json
        items = data.get('items', [])
        cliente_id = data.get('cliente_id')
        
        if not items:
            return jsonify({'success': False, 'message': 'No hay productos en la venta'}), 400
        
        # Crear venta
        venta = Venta(
            usuario_id=current_user.id,
            cliente_id=cliente_id if cliente_id else None,
            estado='completada'
        )
        
        # Agregar detalles
        for item in items:
            producto = Producto.query.get(item['id'])
            
            if not producto:
                return jsonify({'success': False, 'message': f'Producto no encontrado'}), 400
            
            if producto.stock < item['cantidad']:
                return jsonify({'success': False, 'message': f'Stock insuficiente para {producto.nombre}'}), 400
            
            detalle = DetalleVenta(
                producto_id=producto.id,
                cantidad=item['cantidad'],
                precio_unitario=producto.precio
            )
            detalle.calcular_subtotal()
            venta.detalles.append(detalle)
            
            # Actualizar stock
            producto.stock -= item['cantidad']
        
        venta.calcular_totales()
        db.session.add(venta)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'venta_id': venta.id,
            'total': venta.total,
            'message': 'Venta registrada exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# ==================== DASHBOARD ====================

@app.route('/dashboard')
@login_required
def dashboard():
    # Ventas del día
    hoy = datetime.utcnow().date()
    ventas_hoy = Venta.query.filter(func.date(Venta.fecha) == hoy).all()
    total_ventas_hoy = sum(v.total for v in ventas_hoy)

    # Productos más vendidos
    productos_vendidos_query = db.session.query(
        Producto.nombre,
        func.sum(DetalleVenta.cantidad).label('total')
    ).join(DetalleVenta).group_by(Producto.nombre).order_by(desc('total')).limit(5).all()

    productos_vendidos = [(nombre, int(total)) for nombre, total in productos_vendidos_query]

    # Stock bajo
    productos_stock_bajo = Producto.query.filter(
        Producto.stock <= Producto.stock_minimo,
        Producto.activo == True
    ).all()

    # Ventas recientes
    ventas_recientes = Venta.query.order_by(desc(Venta.fecha)).limit(10).all()

    return render_template(
        'dashboard.html',
        total_ventas_hoy=total_ventas_hoy,
        numero_ventas_hoy=len(ventas_hoy),
        productos_vendidos=productos_vendidos,
        productos_stock_bajo=productos_stock_bajo,
        ventas_recientes=ventas_recientes
    )

# ==================== REPORTES ====================

@app.route('/reportes')
@login_required
def reportes():
    return render_template('reportes.html')

@app.route('/reportes/ventas/pdf')
@login_required
def reporte_ventas_pdf():
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    
    query = Venta.query
    
    if fecha_inicio:
        query = query.filter(Venta.fecha >= datetime.strptime(fecha_inicio, '%Y-%m-%d'))
    if fecha_fin:
        query = query.filter(Venta.fecha <= datetime.strptime(fecha_fin, '%Y-%m-%d'))
    
    ventas = query.all()
    
    # Crear PDF
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 750, "TechStore POS - Reporte de Ventas")
    
    p.setFont("Helvetica", 12)
    y = 700
    
    total_general = 0
    for venta in ventas:
        p.drawString(100, y, f"Venta #{venta.id} - {venta.fecha.strftime('%d/%m/%Y %H:%M')}")
        p.drawString(400, y, f"S/ {venta.total:.2f}")
        total_general += venta.total
        y -= 20
        
        if y < 100:
            p.showPage()
            y = 750
    
    p.drawString(100, y - 20, f"Total General: S/ {total_general:.2f}")
    
    p.save()
    buffer.seek(0)
    
    return send_file(buffer, as_attachment=True, download_name='reporte_ventas.pdf', mimetype='application/pdf')

@app.route('/reportes/inventario/excel')
@login_required
def reporte_inventario_excel():
    productos = Producto.query.filter_by(activo=True).all()
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Inventario"
    
    # Encabezados
    ws.append(['ID', 'Nombre', 'Categoría', 'Precio', 'Stock', 'Stock Mínimo', 'Estado'])
    
    # Datos
    for p in productos:
        estado = 'Stock Bajo' if p.stock_bajo else 'OK'
        ws.append([p.id, p.nombre, p.categoria, p.precio, p.stock, p.stock_minimo, estado])
    
    # Guardar en buffer
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    return send_file(buffer, as_attachment=True, download_name='inventario.xlsx', 
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)