import os

# Usamos comillas simples (''') para los bloques de código dentro del texto
# para evitar que la interfaz visual de chat se rompa al leerlo.
readme_content = """# 💧 AquaSpain: Dashboard del Estado de los Embalses en España

AquaSpain es una aplicación web interactiva que permite visualizar el estado actual y la evolución histórica de las reservas de agua en los embalses españoles. 

El proyecto cuenta con un sistema **100% automatizado** (ETL) que extrae, limpia y optimiza los datos directamente desde las bases de datos oficiales del Ministerio para la Transición Ecológica y el Reto Demográfico (MITECO), publicando la web sin intervención manual.

---

## ✨ Características Principales

* **Actualización Autónoma:** Un bot revisa semanalmente si hay nuevos datos publicados por el Ministerio y actualiza la web automáticamente.
* **Eficiencia Energética (Smart Hash):** El pipeline comprueba la firma (Hash SHA-256) del archivo origen. Si no hay cambios, aborta la ejecución para ahorrar recursos.
* **JSON Optimizado:** Los datos se procesan con `pandas` para calcular medias históricas y se comprimen en un formato híbrido que hace que la web cargue a la velocidad del rayo.
* **Despliegue Continuo (CI/CD):** Alojado en Cloudflare Pages con integración directa a GitHub.

---

## 🏗️ Arquitectura del Proyecto

El proyecto se divide en tres pilares fundamentales:

1. **Frontend (La Web):** Construido con React y empaquetado con Vite.
2. **ETL (El Motor de Datos):** Script en Python (`etl/etl.py`) que descarga un `.zip` del Ministerio, extrae las tablas `.mdb` usando `mdbtools`, formatea fechas y calcula estadísticas.
3. **Automatización (CI/CD):** Orquestado con GitHub Actions (`.github/workflows/etl-miteco.yml`).

---

## 🛠️ Instalación y Despliegue Local

### 1. Clonar el repositorio
'''bash
git clone https://github.com/fjmahv/aquaspain.git
cd aquaspain
'''

### 2. Levantar el Frontend (Web)
Necesitas tener instalado [Node.js](https://nodejs.org/).
'''bash
npm install
npm run dev
'''

### 3. Ejecutar la ETL (Python) manualmente
**Requisito indispensable del sistema operativo:**
Debes instalar la librería que lee bases de datos Access (`mdbtools`):
* **Mac (Homebrew):** `brew install mdbtools`
* **Linux (Ubuntu/Debian):** `sudo apt-get install mdbtools`

**Instalar dependencias y ejecutar:**
'''bash
pip install -r requirements.txt
python etl/etl.py
'''

---

## 📁 Estructura del Repositorio

'''text
aquaspain/
├── .github/workflows/      # Configuración del robot de automatización
├── public/                 # Archivos estáticos y JSON de datos
│   └── datos_embalses_optimizado.json
├── src/                    # Código fuente del frontend (React)
├── etl/                    # Scripts de procesamiento de datos
│   └── etl.py              # Script principal
├── requirements.txt        # Dependencias de Python
└── README.md               # Esta documentación
'''

---

## 📊 Origen de los Datos

Los datos brutos son generados por el **Ministerio para la Transición Ecológica y el Reto Demográfico (MITECO)** a través del Boletín Hidrológico Peninsular.
* **Enlace origen:** [Histórico de embalses MITECO](https://www.miteco.gob.es/es/agua/temas/evaluacion-de-los-recursos-hidricos/boletin-hidrologico/Historico-de-embalses.html)

*Disclaimer: Esta aplicación es un proyecto independiente y no tiene vinculación oficial con el MITECO.*
"""

def main():
    # Aquí Python convierte las comillas simples de vuelta al formato 
    # original de Markdown (tres acentos graves) antes de guardar el archivo.
    contenido_final = readme_content.replace("'''", "`" * 3)
    
    try:
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(contenido_final)
        print("✅ ¡Éxito! El archivo README.md ha sido generado correctamente en la carpeta actual.")
        print("Puedes borrar este script de Python si ya no lo necesitas.")
    except Exception as e:
        print(f"❌ Ha ocurrido un error al intentar crear el archivo: {e}")

if __name__ == "__main__":
    main()