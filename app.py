import streamlit as st
import tempfile
import os
import io
import base64
import trimesh
from PIL import Image
from gradio_client import Client, handle_file
import streamlit.components.v1 as components

st.set_page_config(page_title="2D to 3D STL Üretici", page_icon="🗿", layout="wide")
st.title("🗿 2D'den 3D'ye STL Üretici (Hatasız Sürüm)")
st.info("💡 Fotoğrafınız sunucuyu çökertmemesi için otomatik optimize edilir.")

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
        with st.spinner("Görsel optimize ediliyor ve 3D model örülüyor... (Lütfen bekleyin)"):
            try:
                # 1. Görseli GPU'yu çökertmeyecek boyuta getir (Maksimum 1024x1024)
                img = Image.open(uploaded_file)
                img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    img.save(tmp.name, format="PNG")
                    optimized_path = tmp.name

                # 2. Stability AI Stable Fast 3D'ye bağlan
                client = Client("stabilityai/stable-fast-3d")
                result = client.predict(
                    input_image=handle_file(optimized_path),
                    remesh_option="None",
                    vertex_count=-1,
                    texture_size=1024,
                    api_name="/run_button"
                )

                # Sonuç dosyasını bul
                if isinstance(result, (list, tuple)):
                    model_path = result[0]
                elif isinstance(result, dict):
                    model_path = result.get("path") or result.get("name")
                else:
                    model_path = str(result)

                if model_path and os.path.exists(model_path):
                    st.success("🎉 3D Modeliniz Başarıyla Oluşturuldu!")

                    with open(model_path, "rb") as f:
                        glb_bytes = f.read()

                    # 3D Görüntüleyici
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

                    # STL'e dönüştür
                    scene_or_mesh = trimesh.load(model_path, file_type='glb')
                    if isinstance(scene_or_mesh, trimesh.Scene):
                        meshes = [g for g in scene_or_mesh.geometry.values() if isinstance(g, trimesh.Trimesh)]
                        solid_mesh = trimesh.util.concatenate(meshes)
                    else:
                        solid_mesh = scene_or_mesh

                    stl_io = io.BytesIO()
                    solid_mesh.export(stl_io, file_type='stl')
                    stl_bytes = stl_io.getvalue()

                    st.download_button(
                        label="📥 3D Yazıcı İçin STL İndir",
                        data=stl_bytes,
                        file_name="3d_baski_modeli.stl",
                        mime="application/sla",
                        type="primary",
                        use_container_width=True
                    )
                else:
                    st.error("Model dosyası oluşturulamadı.")

            except Exception as e:
                st.error(f"Hata detayı: {str(e)}")
