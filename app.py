import streamlit as st
import requests
import base64
import time
import io
import trimesh
import streamlit.components.v1 as components

# Sayfa Başlığı ve Tasarımı
st.set_page_config(page_title="2D to 3D STL Maker", page_icon="🗿", layout="wide")

st.title("🗿 Kişisel 2D'den 3D'ye Model Üretici")
st.markdown("Fotoğrafınızı yükleyin; yapay zeka **görünmeyen arkasını tamamlayarak** 3D yazıcıya hazır **STL** dosyası üretsin.")

# Sol Panel: Ayarlar ve API Anahtarı
with st.sidebar:
    st.header("⚙️ Ayarlar")
    meshy_api_key = st.text_input(
        "Meshy API Anahtarınız:", 
        type="password",
        help="meshy.ai sitesine ücretsiz üye olup 'API Keys' kısmından aldığınız anahtarı buraya yapıştırın."
    )
    st.markdown("[Buradan ücretsiz Meshy API Key alabilirsiniz](https://app.meshy.ai/settings/api-keys)")
    st.markdown("---")
    st.info("💡 En iyi sonuç için kişileri arka plandan ayırıp (arka plansız PNG) yükleyin.")

# Ana Ekran
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
    st.subheader("2. 3D Model Önizleme & İndirme")
    
    if generate_btn:
        if not meshy_api_key:
            st.error("Lütfen sol menüden Meshy API anahtarınızı girin!")
        else:
            try:
                bytes_data = uploaded_file.getvalue()
                base64_str = base64.b64encode(bytes_data).decode("utf-8")
                data_uri = f"data:image/jpeg;base64,{base64_str}"
                
                headers = {"Authorization": f"Bearer {meshy_api_key.strip()}"}
                payload = {
                    "image_url": data_uri,
                    "enable_pbr": False,
                    "should_remesh": True
                }
                
                with st.spinner("Yapay zeka modeli hazırlıyor... Lütfen bekleyin (1-2 dakika sürer)."):
                    post_res = requests.post("https://api.meshy.ai/v2/image-to-3d", headers=headers, json=payload)
                    
                    if post_res.status_code != 200:
                        st.error(f"API Hatası: {post_res.text}")
                    else:
                        task_id = post_res.json().get("result")
                        progress_bar = st.progress(0, text="Yapay zeka arka kısmı tamamlıyor...")
                        
                        glb_url = None
                        for _ in range(60):
                            time.sleep(5)
                            get_res = requests.get(f"https://api.meshy.ai/v2/image-to-3d/{task_id}", headers=headers)
                            task_data = get_res.json()
                            status = task_data.get("status")
                            progress = task_data.get("progress", 0)
                            
                            progress_bar.progress(progress, text=f"3D Model Üretiliyor: %{progress}")
                            
                            if status == "SUCCEEDED":
                                glb_url = task_data["model_urls"]["glb"]
                                break
                            elif status in ["FAILED", "EXPIRED"]:
                                st.error("Model üretilemedi!")
                                break
                        
                        if glb_url:
                            progress_bar.empty()
                            st.success("🎉 Model başarıyla üretildi!")
                            
                            viewer_html = f"""
                            <script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/3.3.0/model-viewer.min.js"></script>
                            <model-viewer src="{glb_url}" 
                                          auto-rotate 
                                          camera-controls 
                                          style="width: 100%; height: 420px; background-color: #2b2b2b; border-radius: 12px;">
                            </model-viewer>
                            """
                            components.html(viewer_html, height=440)
                            
                            glb_data = requests.get(glb_url).content
                            
                            scene = trimesh.load(io.BytesIO(glb_data), file_type='glb')
                            if isinstance(scene, trimesh.Scene):
                                meshes = [g for g in scene.geometry.values() if isinstance(g, trimesh.Trimesh)]
                                solid_mesh = trimesh.util.concatenate(meshes)
                            else:
                                solid_mesh = scene
                                
                            stl_bytes = solid_mesh.export(file_type='stl')
                            
                            btn_col1, btn_col2 = st.columns(2)
                            with btn_col1:
                                st.download_button(
                                    label="📥 3D Yazıcı İçin STL İndir",
                                    data=stl_bytes,
                                    file_name="3d_baski_modeli.stl",
                                    mime="application/sla",
                                    type="primary",
                                    use_container_width=True
                                )
                            with btn_col2:
                                st.download_button(
                                    label="🎨 Renkli GLB İndir",
                                    data=glb_data,
                                    file_name="renkli_model.glb",
                                    mime="model/gltf-binary",
                                    use_container_width=True
                                )
            except Exception as e:
                st.error(f"Beklenmeyen bir hata oluştu: {str(e)}")
