import os
import re
import streamlit as st
import pandas as pd
import google.generativeai as genai

# 1. Configuración principal de la página web
st.set_page_config(page_title="Biblioteca ePub IA", page_icon="📚", layout="wide")

# 2. Leer la API Key de forma 100% segura (oculta en el servidor)
API_KEY = st.secrets.get("GEMINI_API_KEY", "")
if API_KEY:
    genai.configure(api_key=API_KEY)

# 3. Función optimizada para leer tus 152,000 libros rápidamente
@st.cache_data
def procesar_catalogo(contenido_texto):
    lineas = contenido_texto.split('\n')
    libros = []
    # Usamos la misma lógica que antes para extraer los datos de tu HTML/TXT
    patron = re.compile(r'<a href="([^"]+)">[^<]+</a>\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*)')
    
    for linea in lineas:
        match = patron.search(linea)
        if match:
            libros.append({
                "Título": match.group(4).strip(),
                "Autor": match.group(5).strip(),
                "Año": match.group(2).strip(),
                "Páginas": match.group(3).strip()
            })
    return pd.DataFrame(libros)

# Título de la App
st.title("📚 La Biblioteca ePub de Adolfo")
st.markdown("Explora el catálogo de más de 152,000 ePubs y pide recomendaciones a la IA.")

# 4. Carga automática del catálogo para tus compañeros
catalogo_texto = None
if os.path.exists("indice_titulo.html"):
    with open("indice_titulo.html", "r", encoding="utf-8", errors="ignore") as f:
        catalogo_texto = f.read()
elif os.path.exists("indice_titulo.txt"):
    with open("indice_titulo.txt", "r", encoding="utf-8", errors="ignore") as f:
        catalogo_texto = f.read()

# Si no está en el servidor, mostramos el botón (modo de emergencia)
if not catalogo_texto:
    archivo_subido = st.file_uploader("No se detectó el catálogo en el servidor. Súbelo manualmente:", type=['html', 'txt'])
    if archivo_subido is not None:
        catalogo_texto = archivo_subido.getvalue().decode("utf-8", errors="ignore")

# 5. Interfaz de la aplicación
if catalogo_texto:
    with st.spinner("Procesando los 152,000 libros... esto solo toma un segundo."):
        df_libros = procesar_catalogo(catalogo_texto)
    
    tab1, tab2 = st.tabs(["📖 Explorar Catálogo", "✨ Asistente IA"])
    
    # --- PESTAÑA 1: TABLA Y BÚSQUEDA ---
    with tab1:
        st.subheader("Buscador de Libros")
        busqueda = st.text_input("🔍 Escribe un título o autor para buscar...", "")
        
        if busqueda:
            # Filtra el catálogo súper rápido
            filtro = df_libros[
                df_libros['Título'].str.contains(busqueda, case=False, na=False) | 
                df_libros['Autor'].str.contains(busqueda, case=False, na=False)
            ]
            st.dataframe(filtro, use_container_width=True, hide_index=True)
            st.caption(f"Se encontraron {len(filtro)} resultados.")
        else:
            st.dataframe(df_libros, use_container_width=True, hide_index=True)
            st.caption(f"Mostrando el catálogo completo ({len(df_libros):,} libros).")
            
    # --- PESTAÑA 2: CHAT CON IA ---
    with tab2:
        st.subheader("Chat con la IA Recomendadora")
        
        if not API_KEY:
            st.error("⚠️ La Inteligencia Artificial está desactivada. El administrador debe configurar la variable GEMINI_API_KEY en el servidor.")
        else:
            # Mantener memoria del chat
            if "mensajes" not in st.session_state:
                st.session_state.mensajes = [
                    {"role": "assistant", "content": "¡Hola! Soy el asistente de la biblioteca. Pídeme recomendaciones por género, estado de ánimo o autor. ¿Qué te gustaría leer?"}
                ]
            
            # Mostrar mensajes anteriores y procesar enlaces a catálogo
            for msg in st.session_state.mensajes:
                with st.chat_message(msg["role"]):
                    if msg["role"] == "assistant":
                        # Formateamos el texto para que las etiquetas <libro> se vean en negritas
                        texto_mostrar = re.sub(r'<libro>(.*?)</libro>', r'**\1**', msg["content"], flags=re.IGNORECASE)
                        st.markdown(texto_mostrar)
                        
                        # Extraemos los títulos para crear los "hipervínculos" interactivos
                        libros_mencionados = list(set(re.findall(r'<libro>(.*?)</libro>', msg["content"], flags=re.IGNORECASE)))
                        
                        if libros_mencionados:
                            st.markdown("---")
                            st.caption("🔍 **Acceso rápido al explorador del catálogo:**")
                            for titulo in libros_mencionados:
                                # Creamos un desplegable por cada libro recomendado
                                with st.expander(f"📚 Ver detalles de '{titulo}' en la biblioteca"):
                                    # Usamos regex=False para que no confunda símbolos en el título
                                    filtro_ia = df_libros[
                                        df_libros['Título'].str.contains(titulo, case=False, na=False, regex=False) |
                                        df_libros['Autor'].str.contains(titulo, case=False, na=False, regex=False)
                                    ]
                                    if not filtro_ia.empty:
                                        st.dataframe(filtro_ia, use_container_width=True, hide_index=True)
                                    else:
                                        st.warning("El libro existe pero la búsqueda exacta requiere usar la pestaña 'Explorar Catálogo'.")
                    else:
                        st.markdown(msg["content"])
            
            # Caja de texto para el usuario
            if pregunta := st.chat_input("Ej: Recomiéndame todos los libros de Stephen King..."):
                # Mostrar pregunta del usuario
                st.session_state.mensajes.append({"role": "user", "content": pregunta})
                st.rerun() # Recargar para que aparezca la pregunta inmediatamente antes de pensar
                
            # Si el último mensaje es del usuario, procesamos la respuesta de la IA
            if st.session_state.mensajes[-1]["role"] == "user":
                pregunta_actual = st.session_state.mensajes[-1]["content"]
                with st.chat_message("assistant"):
                    with st.spinner("Revisando la inmensa biblioteca..."):
                        try:
                            # --- NUEVO: PRE-FILTRADO INTELIGENTE ---
                            # Extraemos palabras de la pregunta para asegurar que mandamos al autor correcto a la IA
                            palabras_usuario = re.findall(r'\b\w{4,}\b', pregunta_actual.lower())
                            
                            if palabras_usuario:
                                score = pd.Series(0, index=df_libros.index)
                                textos_busqueda = (df_libros['Título'].fillna('') + " " + df_libros['Autor'].fillna('')).str.lower()
                                
                                for p in palabras_usuario:
                                    score += textos_busqueda.str.contains(p, regex=False).astype(int)
                                
                                df_temp = df_libros.copy()
                                df_temp['score'] = score
                                df_top = df_temp.sort_values(by='score', ascending=False).head(1000)
                                muestra = df_top.drop(columns=['score']).sample(frac=1).reset_index(drop=True)
                            else:
                                muestra = df_libros.sample(n=min(1000, len(df_libros)))

                            catalogo_str = "\n".join([f"- {row['Título']} (por {row['Autor']})" for _, row in muestra.iterrows()])
                            
                            system_prompt = f"""Eres un bibliotecario experto y amigable. Estás hablando con un grupo de compañeros de trabajo que buscan recomendaciones de lectura de una inmensa colección compartida.
                            
                            REGLAS ESTRICTAS:
                            1. RECOMIENDA SOLO libros que estén en el catálogo adjunto.
                            2. OBLIGATORIO: Cada vez que menciones el título de un libro, debes envolverlo con las etiquetas <libro> y </libro>. Ejemplo: Te recomiendo leer <libro>El Resplandor</libro>.
                            3. BÚSQUEDA GENERAL: Si piden recomendaciones por género o trama, da 5 o 6 sugerencias breves y explica por qué.
                            4. BÚSQUEDA POR AUTOR: Si el usuario te pregunta por un AUTOR, DEBES IGNORAR el límite de 5 o 6 y hacer una LISTA COMPLETA de TODOS los libros de ese autor que encuentres en tu catálogo.
                            
                            CATÁLOGO DISPONIBLE:
                            {catalogo_str}"""
                            
                            prompt_completo = f"[INSTRUCCIONES DEL SISTEMA]:\n{system_prompt}\n\n[CONSULTA DEL USUARIO]:\n{pregunta_actual}"
                            
                            # Búsqueda dinámica de modelo
                            modelo_valido = 'gemini-1.5-flash'
                            try:
                                para_usar = None
                                for m in genai.list_models():
                                    if 'generateContent' in m.supported_generation_methods:
                                        if '1.5-flash' in m.name:
                                            para_usar = m.name
                                            break
                                        elif not para_usar:
                                            para_usar = m.name
                                if para_usar:
                                    modelo_valido = para_usar
                            except Exception:
                                pass
                            
                            modelo = genai.GenerativeModel(modelo_valido)
                            respuesta = modelo.generate_content(prompt_completo)
                            
                            texto_respuesta = respuesta.text
                            st.session_state.mensajes.append({"role": "assistant", "content": texto_respuesta})
                            st.rerun() # Recargamos para que se renderice el texto y los expanders del catálogo
                            
                        except Exception as e:
                            st.error(f"¡Ups! Hubo un fallo en la conexión con la IA: {e}")
                            st.session_state.mensajes.pop() # Quitamos el mensaje del usuario si falla para que intente de nuevo
else:
    st.info("Esperando catálogo...")
