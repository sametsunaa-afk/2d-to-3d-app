import streamlit as st
import tempfile
import os
import io
import base64
import trimesh
from gradio_client import Client, handle_file
import streamlit.components.v1 as components

# Sayfa Ayarları
st.set_page_config(page_title="2D to 3D STL Üretici", page_icon="🗿", layout="wide")

st.title("🗿 Ücretsiz 2D'den 3D'ye STL Üretici (Stable Fast 3D)")
st.info("🎉 Bu sistem en güncel açık kaynaklı Stability AI altyapısını kullanır. API Key veya ücret gerektirmez!")

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
        with st.spinner("Yapay zeka 3D modeli örüyor... (Yaklaşık 10-20 saniye sürer)"):
            try:
                # Geçici dosya oluştur
                suffix = os.path.splitext(uploaded_file.name)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name

                # En güncel Stability AI Stable-Fast-3D sunucusuna bağlan
                client = Client("stabilityai/stable-fast-3d")
                result = client.predict(
                    input_image=handle_file(tmp_path),
                    foreground_ratio=0.85,
                    remesh_option="None",
                    vertex_count=-1,
                    texture_size=1024,
                    api_name="/run_button"
                )

                # Üretilen 3D dosyanın (GLB) yolunu al
                if isinstance(result, (list, tuple)):
                    model_path = result[0]
                elif isinstance(result, dict):
                    model_path = result.get("path") or result.get("name")
                else:
                    model_path = str(result)

                if model_path and os.path.exists(model_path):
                    st.success("🎉 3D Modeliniz başarıyla oluşturuldu!")

                    # Modeli oku
                    with open(model_path, "rb") as f:
                        glb_bytes = f.read()

                    # 3D Canlı Görüntüleyici (Ekranda 360 derece döndürme)
                    glb_b64 = base64.b64encode(glb_bytes).decode("utf-8")
                    viewer_html = f"""
                    <script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/3.3.0/model-viewer.min.js"></script>
                    <model-viewer src="data:model/gltf-binary;base64,{glb_b64}" 
                                  auto-rotate 
                                  camera-controls 
                                  style="width: 100%; height: 420px; background-color: #2b2b2b; border-radius: 12px;">
                    </model-viewer>
                    """
                    components.html(viewer_html, height=440)

                    # 3D Yazıcı için STL'e dönüştür
                    scene_or_mesh = trimesh.load(model_path, file_type='glb')
                    if isinstance(scene_or_mesh, trimesh.Scene):
                        meshes = [g for g in scene_or_mesh.geometry.values() if isinstance(g, trimesh.Trimesh)]
                        solid_mesh = trimesh.util.concatenate(meshes)
                    else:
                        solid_mesh = scene_or_mesh

                    stl_io = io.BytesIO()
                    solid_mesh.export(stl_io, file_type='stl')
                    stl_bytes = stl_io.getvalue()

                    # İndirme Butonları
                    btn1, btn2 = st.columns(2)
                    with btn1:
                        st.download_button(
                            label="📥 3D Yazıcı İçin STL İndir",
                            data=stl_bytes,
                            file_name="3d_baski_modeli.stl",
                            mime="application/sla",
                            type="primary",
                            use_container_width=True
                        )
                    with btn2:
                        st.download_button(
                            label="🎨 Renkli GLB İndir",
                            data=glb_bytes,
                            file_name="model_renkli.glb",
                            mime="model/gltf-binary",
                            use_container_width=True
                        )
                else:
                    st.error("Model dosyası oluşturulamadı.")

            except Exception as e:
                st.error(f"İşlem sırasında bir hata oluştu: {str(e)}")
