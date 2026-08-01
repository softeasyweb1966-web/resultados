# Módulo Dinámico de Resultados de Laboratorio

Módulo independiente para gestión y emisión de resultados de laboratorio clínico,  
construido con **Python · Flask · SQLAlchemy · PostgreSQL · Pandas · ReportLab**.

---

## Características

| Área | Funcionalidad |
|------|--------------|
| **Diseño de plantillas** | Editor tipo Excel con combinación de filas/columnas, 6 tipos de celda (encabezado, etiqueta, resultado, fijo, unidades, vacío), negrita, alineación, vista previa en tiempo real |
| **Catálogo de exámenes** | CRUD de exámenes con código, técnica, equipo, método, tipo de muestra; compatible con laboratorio humano y veterinario |
| **Parámetros** | Tipo entero / decimal / texto; valores de referencia por género y rango de edad (valor exacto, rango mín–máx, texto); unidades configurables |
| **Registro de resultados** | Búsqueda por consecutivo/orden y código de examen, resaltado de campos editables, bloqueo de campos fijos, alarma visual para valores fuera de rango, botón de resultado anterior |
| **Firmas** | Bacteriólogo obligatorio, revisor/aprobador opcional; imágenes de firma en PDF |
| **PDF** | Generado con ReportLab; logo institucional, encabezado, pie de página, tabla de resultados con colores de alarma, firmas, código QR de verificación |
| **Verificación QR** | URL pública `/results/verify/<token>` para comprobar autenticidad del resultado |
| **Configuración PDF** | Por usuario: institución, logo, márgenes, tamaño de página, QR, marca de agua |
| **Seguridad** | Autenticación con Flask-Login, roles (admin / bacteriólogo / revisor), hashing de contraseñas |

---

## Requisitos previos

- Python 3.10+
- PostgreSQL 14+
- pip

---

## Instalación rápida

```bash
# 1. Clonar / ubicarse en el directorio del módulo
cd resultados

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con su DATABASE_URL y SECRET_KEY

# 5. Crear la base de datos en PostgreSQL
psql -U postgres -c "CREATE DATABASE resultados_db;"

# 6. Aplicar migraciones
flask db init          # solo la primera vez
flask db migrate -m "Estructura inicial"
flask db upgrade

# 7. Crear usuario administrador inicial
flask shell
>>> from app import db
>>> from app.models import User
>>> u = User(username='admin', name='Administrador', role='admin')
>>> u.set_password('admin123')
>>> db.session.add(u)
>>> db.session.commit()
>>> exit()

# 8. Iniciar servidor de desarrollo
flask run
```

Abrir el navegador en **http://localhost:5000**

---

## Estructura del proyecto

```
resultados/
├── app/
│   ├── __init__.py          # factory create_app()
│   ├── models.py            # User, Exam, Parameter, ReferenceValue,
│   │                        # LayoutCell, Order, Patient, Result,
│   │                        # ParameterResult, PDFConfig
│   ├── routes/
│   │   ├── auth.py          # login, logout, perfil, CRUD usuarios
│   │   ├── exams.py         # catálogo de exámenes + parámetros
│   │   ├── designer.py      # editor de plantilla (grid)
│   │   ├── results.py       # registro y consulta de resultados
│   │   ├── orders.py        # órdenes y pacientes
│   │   ├── pdf_config.py    # configuración de PDF
│   │   ├── api.py           # endpoints AJAX (búsquedas, prev. resultados)
│   │   └── main.py          # panel principal
│   ├── services/
│   │   ├── reference_checker.py   # validación de valores de referencia
│   │   └── pdf_generator.py       # generación PDF con ReportLab + QR
│   ├── static/
│   │   ├── css/main.css
│   │   └── uploads/         # logos, firmas (excluido de git)
│   └── templates/           # Jinja2 + Bootstrap 5
├── config.py                # DevelopmentConfig / ProductionConfig
├── run.py                   # entry point + shell context
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Variables de entorno

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `SECRET_KEY` | Clave secreta Flask (cambie en producción) | `s3cr3t-k3y` |
| `DATABASE_URL` | URL de conexión PostgreSQL | `******localhost:5432/resultados_db` |
| `FLASK_ENV` | Entorno | `development` / `production` |

---

## Flujo de uso

1. **Administrador** define exámenes (código, nombre, técnica, equipo, método)  
2. Agrega **parámetros** a cada examen (tipo de resultado, unidades, valores de referencia por edad/género)  
3. Diseña la **plantilla visual** del examen en el editor de cuadrícula (combinar celdas, asignar tipo y parámetro)  
4. **Bacteriólogo** busca la orden por consecutivo → selecciona el examen → ingresa los resultados  
   - El sistema muestra alarma si el valor está fuera del rango de referencia  
   - Se puede consultar el resultado anterior del mismo paciente  
   - Firma el resultado; puede agregar un revisor  
5. Finaliza el resultado → genera **PDF** con QR  
6. El PDF puede verificarse escaneando el QR (URL pública de verificación)

---

## Integración con otros sistemas

El módulo está diseñado como una aplicación Flask independiente.  
Para integrarlo a un sistema existente:

- Registrar los `Blueprint` de `app/routes/` en la aplicación principal  
- Compartir la instancia de `db` (SQLAlchemy) o configurar una Base separada  
- Los modelos de `Patient`, `Order` pueden mapearse/reemplazarse con los de la aplicación host  
- La generación de PDF (`services/pdf_generator.py`) es completamente independiente

---

## Producción

```bash
gunicorn "run:app" --workers 4 --bind 0.0.0.0:8000
```

Asegúrese de:
- Configurar un proxy inverso (Nginx/Apache)
- Usar `SECRET_KEY` aleatoria y segura
- Mantener el directorio `uploads/` fuera del control de versiones y con respaldo
