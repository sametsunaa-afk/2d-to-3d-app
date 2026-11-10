import streamlit as st
import requests
import time
import io
import os
import base64
import trimesh
from PIL import Image
import streamlit.components.v1 as components

st.set_page_config(page_title="2D to 3D STL Üretici", page_icon="🗿", layout="wide")

st.title("🗿 2D'den 3D'ye STL Üretici (Tripo3D Motoru)")
st.markdown("Fotoğrafınızı yükleyin; yapay zeka **görünmeyen arkasını tamamlayarak** 3D yazıcıya hazır **STL** dosyası üretsin.")

# Sol Panel
with st.sidebar:
    st.header("⚙️ Ayarlar")
    tripo_api_key = st.text_input(
        "Tripo3D API Anahtarınız (tsk_...):", 
        type="password",
        help="platform.tripo3d.ai adresinden alacağınız ücretsiz anahtar."
    )
    st.markdown("👉 **[Buradan Ücretsiz Tripo API Key Alın](https://platform.tripo3d.ai/api-keys)**")
    st.caption("Google ile giriş yapın, soldaki 'API Keys' kısmından anahtarınızı kopyalayın.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Fotoğrafı Yükleyin")
    uploaded_file = st.file_uploader("Görsel seçin (JPG veya PNG)", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Yüklenen Görsel", use_container_width=True)
        generate_btn = st.button("🚀 3D Modeli ve Arkasını Oluştur", type="primary")
    else:
        generate_btn = False

with col2:
    st.subheader("2. 3D Model ve STL İndirme")
    if generate_btn and uploaded_file is not None:
        if not tripo_api_key:
            st.error("Lütfen sol menüden Tripo3D API anahtarınızı (tsk_...) girin!")
        else:
            api_key = tripo_api_key.strip()
            headers = {"Authorization": f"Bearer {api_key}"}
            
            with st.spinner("Fotoğraf optimize ediliyor ve yapay zekaya yükleniyor..."):
                try:
                    # Görseli optimize et
                    img = Image.open(uploaded_file)
                    img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                    img_bytes_io = io.BytesIO()
                    img.save(img_bytes_io, format="PNG")
                    img_bytes = img_bytes_io.getvalue()
                    
                    # 1. Dosyayı Tripo'ya Yükle
                    upload_url = "https://api.tripo3d.ai/v2/openapi/upload"
                    files = {"file": ("input.png", img_bytes, "image/png")}
                    upload_res = requests.post(upload_url, headers=headers, files=files)
                    
                    if upload_res.status_code != 200:
                        st.error(f"Yükleme hatası ({upload_res.status_code}): {upload_res.text}")
                    else:
                        upload_data = upload_res.json()
                        image_token = upload_data.get("data", {}).get("image_token")
                        
                        if not image_token:
                            st.error(f"Görsel tokenı alınamadı: {upload_data}")
                        else:
                            # 2. 3D Üretim Görevini Başlat
                            task_url = "https://api.tripo3d.ai/v2/openapi/task"
                            task_payload = {
                                "type": "image_to_model",
                                "file": {
                                    "type": "png",
                                    "file_token": image_token
                                }
                            }
                            task_res = requests.post(
                                task_url, 
                                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, 
                                json=task_payload
                            )
                            
                            if task_res.status_code != 200:
                                st.error(f"Görev başlatma hatası: {task_res.text}")
                            else:
                                task_id = task_res.json().get("data", {}).get("task_id")
                                progress_bar = st.progress(0, text="Yapay zeka 3D modeli örüyor...")
                                
                                # 3. Model Tamamlanana Kadar Bekle
                                glb_url = None
                                for _ in range(60): # Maksimum 3-4 dakika
                                    time.sleep(4)
                                    status_res = requests.get(f"https://api.tripo3d.ai/v2/openapi/task/{task_id}", headers=headers)
                                    if status_res.status_code == 200:
                                        status_data = status_res.json().get("data", {})
                                        current_status = status_data.get("status")
                                        progress = status_data.get("progress", 0)
                                        
                                        progress_bar.progress(progress, text=f"3D Model Üretiliyor: %{progress}")
                                        
                                        if current_status == "success":
                                            output = status_data.get("output", {})
                                            glb_url = output.get("pbr_model") or output.get("model")
                                            break
                                        elif current_status in ["failed", "cancelled"]:
                                            st.error("Model üretimi başarısız oldu.")
                                            break
                                
                                if glb_url:
                                    progress_bar.empty()
                                    st.success("🎉 3D Modeliniz başarıyla tamamlandı!")
                                    
                                    # GLB'yi indir
                                    glb_data = requests.get(glb_url).content
                                    
                                    # 3D Görüntüleyici
                                    glb_b64 = base64.b64encode(glb_data).decode("utf-8")
                                    viewer_html = f"""
                                    <script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/3.3.0/model-viewer.min.js"></script>
                                    <model-viewer src="data:model/gltf-binary;base64,{glb_b64}" 
                                                  auto-rotate 
                                                  camera-controls 
                                                  style="width: 100%; height: 420px; background-color: #2b2b2b; border-radius: 12px;">
                                    </model-viewer>
                                    """
                                    components.html(viewer_html, height=440)
                                    
                                    # STL'e dönüştür
                                    scene_or_mesh = trimesh.load(io.BytesIO(glb_data), file_type='glb')
                                    if isinstance(scene_or_mesh, trimesh.Scene):
                                        meshes = [g for g in scene_or_mesh.geometry.values() if isinstance(g, trimesh.Trimesh)]
                                        solid_mesh = trimesh.util.concatenate(meshes)
                                    else:
                                        solid_mesh = scene_or_mesh
                                        
                                    stl_io = io.BytesIO()
                                    solid_mesh.export(stl_io, file_type='stl')
                                    stl_bytes = stl_io.getvalue()
                                    
                                    # İndirme Butonları
                                    b1, b2 = st.columns(2)
                                    with b1:
                                        st.download_button(
                                            label="📥 3D Yazıcı İçin STL İndir",
                                            data=stl_bytes,
                                            file_name="3d_baski_modeli.stl",
                                            mime="application/sla",
                                            type="primary",
                                            use_container_width=True
                                        )
                                    with b2:
                                        st.download_button(
                                            label="🎨 Renkli GLB İndir",
                                            data=glb_data,
                                            file_name="model_renkli.glb",
                                            mime="model/gltf-binary",
                                            use_container_width=True
                                        )
                except Exception as e:
                    st.error(f"Hata detayı: {str(e)}")
